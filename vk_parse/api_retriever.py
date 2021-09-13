from vk_parse.models import Group, Post, User, Comment, db_engine

import configparser
import datetime
import logging
import sys

import requests
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

start_time = datetime.datetime.now()
config = configparser.ConfigParser()
config.read('../config.cfg')

session = Session(db_engine)
base_url = 'https://api.vk.com/method/wall.get?v=5.95&'
token = config.get('vk', 'token')

logging.basicConfig(
    filename='tw_analyse.log',
    format=' [%(asctime)s] %(filename)s[LINE:%(lineno)d]# '
           '%(levelname)-8s %(message)s',
    level=logging.INFO
)

def get_comments(group_id: str, p_ids: list, rq_limit=4500):
    """Get comments for a limited amount of posts per day."""
    req_url = 'https://api.vk.com/method/wall.getComments?v=5.95&'
    req_url += f'access_token={token}&owner_id=-{group_id}&count=100'

    urls, post_comments = [], []
    for p_id in p_ids:
        urls.append(req_url + f'&post_id={p_id}')
    offset, count = 0, 200
    for url in urls:
        while rq_limit > 0 and count > offset:
            urlo = url + f'&offset={offset}'
            response = requests.get(urlo).json()
            count = response['response']['count']
            response = response['response']['items']
            for item in response:
                post_comments.append(Comment(
                    id=item['id'],
                    from_id=item['from_id'],
                    post_id=item['post_id'],
                    owner_id=group_id,
                    date=datetime.datetime.fromtimestamp(item['date']),
                    text=item['text']
                ))
            offset += 100
            rq_limit -= 1
            print(f'Request limit: {rq_limit}')
            print(f'Offset: {offset}')
        session.add_all(post_comments)
        session.commit()
    return post_comments

def get_user(user_id):
    """Get and check for existance user's instance."""
    user = session.query(User).filter_by(id=user_id).scalar()
    if user:
        return user
    req_url = 'https://api.vk.com/method/users.get?v=5.95&'
    req_url += f'access_token={token}&user_ids={user_id}'
    response = requests.get(req_url).json()
    response = response['response'][0]
    user = User(
        id=response['id'],
        first_name=response['first_name'],
        last_name=response['last_name'],
        deactivated=response['deactivated'],
        is_closed=response['is_closed'],
        about=response['about']
    )
    return user

def get_group(group_id):
    """Get and check for existance group (vk.com/clubID)."""
    group = session.query(Group).filter_by(id=group_id).scalar()
    if group:
        return group
    req_url = f'https://api.vk.com/method/groups.getById?v=5.95&' \
              f'access_token={token}&group_id={group_id}&' \
              f'fields=description,is_closed,contacts,members_count,links'
    response = requests.get(req_url).json()
    if 'error' in response.keys():
        response = response['error']
        if response.get('error_code') == 5:
            sys.exit('Auth token has expired, please go and get a new one.')
    response = response['response'][0]
    contacts = response.get('contacts', None)
    users = []
    if contacts:
        for contact in contacts:
            if contacts and contact.get('user_id', None):
                uids = contact.get('user_id')
                for uid in uids:
                    users.append(get_user(uid))
        session.bulk_save_objects(users)
    group = Group(
        id=response['id'],
        name=response['name'],
        screen_name=response['screen_name'],
        is_closed=response.get('is_closed',None),
        description=response.get('description',None)
    )
    session.add(group)
    session.commit()
    return group

def get_posts(owner_id, req_limit=5000):
    offset = 0
    try:
        max_post_id = session.query(func.max(Post.post_id)).filter(
            Post.owner_id == owner_id
        ).one()[0]
    except NoResultFound:
        max_post_id = 0
    get_group(owner_id)
    posts = []
    while req_limit > 0 and (not posts or posts[-1]['id'] > max_post_id[0]):
        req_group_url = f'https://api.vk.com/method/wall.get?v=5.95&' \
                        f'access_token={token}&owner_id=-{owner_id}&' \
                        f'offset={offset}&count=100'
        response_r = requests.get(req_group_url)
        response = response_r.json()
        response = response['response']['items']
        if not response:
            break
        for post in response:
            if post['id'] > max_post_id:
                pub_date = datetime.datetime.fromtimestamp(post['date'])
                posts.append(Post(
                    post_id=post['id'],
                    owner_id=owner_id,
                    date=pub_date,
                    marked_as_ads=post['marked_as_ads'],
                    post_type=post['post_type'],
                    text=post['text'],
                    likes_count=post['likes']['count'],
                    repost_count=post['reposts']['count'],
                    views_count=post['views']['count'],
                ))
        offset += 100
        req_limit -= 1
        print(f'Request limit: {req_limit}')
        print(f'Offset: {offset}')
    session.add_all(posts)
    session.commit()
    return posts

def main():
    Comment.__table__.create(db_engine)
    owner_id=config.get('vk', 'group_id')

    # Get the last existing post id for further retrieve
    # posts = get_posts(owner_id)
    # posts = session.query(Post).options(joinedload(Post.group)).limit(50).all()
    posts = session.query(Post).filter(Post.owner_id==owner_id).all()
    post_ids = [post.post_id for post in posts]
    get_comments(owner_id, post_ids)
    a = 1

    session.close()
    print('Performing bulk insert')
    print(f'Successfully finished!')
    print(f'Execution time: ', datetime.datetime.now()-start_time)

if __name__ == '__main__':
    main()
