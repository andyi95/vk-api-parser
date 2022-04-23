import configparser
import datetime
import logging
import sys

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from vk_parse.api_retriever import session
from vk_parse.models import Comment, Group, Post, User, config, db_engine


def main():
    token = config.get('vk', 'token')
    owner_id=config.get('vk', 'group_id')
    req_limit = 4900
    offset = 0
    # Get the last post's date to start retrieving with
    min_date = session.query(func.min(Post.date)).filter(
        Post.owner_id == owner_id
    ).one()
    min_date = min_date[0]
    pub_date = datetime.datetime(2021, 9, 9, 6)
    posts = []
    while pub_date >= min_date and req_limit > 0:
        req_group_url = f'https://api.vk.com/method/wall.get?v=5.95&' \
                        f'access_token={token}&owner_id=-{owner_id}&' \
                        f'offset={offset}&count=100'
        response_r = requests.get(req_group_url)
        response = response_r.json()
        response = response['response']['items']

        for post in response:
            pub_date = datetime.datetime.fromtimestamp(post['date'])
            t = session.query(Post).filter(
                Post.owner_id==owner_id,
                Post.post_id==post['id']
            ).update({Post.comment_count: post['comments']['count']})
            a = 1
        session.commit()
        offset += 100
        req_limit -= 1
        session.close()
if __name__ == '__main__':
    main()