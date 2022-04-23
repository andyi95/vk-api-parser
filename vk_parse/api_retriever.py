import datetime
import logging
import sys
import time
from typing import List

import requests
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session, joinedload
from vk_parse.models import Comment, Group, Post, User, db_engine
import os

from dotenv import load_dotenv
start_time = datetime.datetime.now()


load_dotenv()

session = Session(db_engine)
base_url = 'https://api.vk.com/method/wall.get?v=5.95&'
token = os.getenv('API_TOKEN')

logging.basicConfig(
    filename='tw_analyse.log',
    format=' [%(asctime)s] %(filename)s[LINE:%(lineno)d]# '
           '%(levelname)-8s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger()

def get_comments(group_id: str, p_ids: List[Post], rq_limit=4500):
    """Get comments for a limited amount of posts per day."""
    req_url = 'https://api.vk.com/method/wall.getComments?v=5.95&'
    req_url += f'access_token={token}&owner_id=-{group_id}&count=100'

    urls, post_comments = [], []
    for p_id in p_ids:
        offset, count = 0, 100
        while rq_limit > 0 and count > 1:
            url = req_url + f'&post_id={p_id.post_id}'
            urlo = url + f'&offset={offset}'
            response = requests.get(urlo).json()
            if 'error' in response.keys():
                print(f'Error occured fetching API, retrying in 3 seconds')
                time.sleep(3)
                response = requests.get(urlo).json()
            count = response['response']['count']
            response = response['response']['items']
            if not response:
                break
            for item in response:
                if session.query(Comment).filter_by(id=item['id']).scalar():
                    continue
                author_id = item['from_id'] if item.get('from_id', 0) != 0 else None
                if author_id:
                    author = get_user(author_id)
                post_comments.append(Comment(
                    id=item['id'],
                    from_id=author_id,
                    post_id=p_id.id,
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
        post_comments = []
    return post_comments

def get_user(user_id):
    """Get and check for existance user's instance."""
    user = session.query(User).filter_by(id=user_id).scalar()
    if user:
        return user
    req_url = 'https://api.vk.com/method/users.get?v=5.95&'
    req_url += f'access_token={token}&user_ids={user_id}'
    response = requests.get(req_url).json()
    try:
        response = response['response'][0]
    except (KeyError, IndexError):
        time.sleep(3)
        response = response.get('response')
        if not response or not isinstance(response, list):
            response = {'id': user_id}
        else:
            response = response[0]
    user = User(
        id=response['id'],
        first_name=response.get('first_name', ''),
        last_name=response.get('last_name', ''),
        deactivated=True if response.get('deactivated', False) else False,
        is_closed=True if response.get('is_closed', False) else False,
        about=response.get('about', '')
    )
    session.add(user)
    session.commit()
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

def get_posts(owner_id, req_limit=4800):
    offset = 0
    try:
        max_post_id = session.query(func.max(Post.post_id)).filter(
            Post.owner_id == owner_id
        ).one()[0]
    except NoResultFound:
        max_post_id = 0
    if not max_post_id:
        max_post_id = 0
    get_group(owner_id)
    posts = []
    while req_limit > 0 and (not posts or posts[-1].post_id > max_post_id):
        req_group_url = f'https://api.vk.com/method/wall.get?v=5.95&' \
                        f'access_token={token}&owner_id=-{owner_id}&' \
                        f'offset={offset}&count=100'
        response_r = requests.get(req_group_url)
        response = response_r.json()
        if not 'response' in response:
            print('could not get response')
            print(response)
            time.sleep(3)
            response_r = requests.get(req_group_url)
            response = response_r.json()
        response = response['response']['items']
        if not response or response is None:
            break
        for post in response:
            if post['id'] > max_post_id:
                pub_date = datetime.datetime.fromtimestamp(post['date'])
                try:
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
                except:
                    break
        offset += 100
        req_limit -= 1
        print(f'Request limit: {req_limit}')
        print(f'Offset: {offset}')
        try:
            session.add_all(posts)
            session.commit()
        except IntegrityError as e:
            logger.warning(e.detail)
    return posts

def main():
    # Comment.__table__.create(db_engine)
    ids = os.getenv('GROUP_IDS').split(',')
    # Get the last existing post id for further retrieve
    for owner_id in ids:
        posts = get_posts(owner_id)
        # posts = session.query(Post).filter(
        #     Post.owner_id == owner_id
        # ).all()
        post_ids = [post.post_id for post in posts]
        get_comments(owner_id, posts)

    session.close()
    print(f'Successfully finished!')
    print(f'Execution time: ', datetime.datetime.now()-start_time)

if __name__ == '__main__':
    main()
