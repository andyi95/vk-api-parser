"""Describe data models and their relations."""
import configparser
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, MetaData,
    PrimaryKeyConstraint, Table, UniqueConstraint, create_engine, inspect
)
from sqlalchemy.types import Date, String, Text, SmallInteger, Integer
from sqlalchemy.orm import (
    declarative_base, declared_attr, relationship,
    sessionmaker
)
from sqlalchemy.sql import func

Base = declarative_base()

config = configparser.ConfigParser()
config.read('../config.cfg')
logging.basicConfig(
    filename='../orm_models.log',
    format=' [%(asctime)s] %(filename)s[LINE:%(lineno)d]# '
           '%(levelname)-8s %(message)s',
    level=logging.INFO
)
user = os.getenv('DB_USER', 'postgres')
password = os.getenv('DB_PASSWORD', 'postgres')
host = os.getenv('DB_HOST', 'postgres')
database = os.getenv('DB_NAME', 'vk_posts')
db_string = f'postgresql://{user}:{password}@{host}/{database}'
db_engine = create_engine(db_string)

def get_or_create(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if not instance:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
    return instance

class CustomBase(Base):
    """Custom common class for potential addition of prefix to tbls names."""
    __abstract__ = True

    @declared_attr
    def __tablename__(cls):
        return cls.__inittablename__

class User(CustomBase):
    __inittablename__ = 'users'

    id = Column(Integer, primary_key=True)
    first_name = Column(String(255))
    last_name = Column(String(255))
    deactivated = Column(Boolean, default=False)
    is_closed = Column(Boolean, default=True)
    about = Column(String, nullable=True)
    activities = Column(Text, nullable=True)
    bdate = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    def __repr__(self):
        return f'User id {self.id}, {self.first_name} {self.last_name}'

group_contacts = Table('groupcontacts', Base.metadata,
                       Column('group_id', ForeignKey('groups.id'), primary_key=True),
                       Column('user_id', ForeignKey('users.id'), primary_key=True)
                       )

class Group(CustomBase):
    __inittablename__ = 'groups'

    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String)
    screen_name = Column(String(255))
    is_closed = Column(Boolean, default=False)
    description = Column(Text)
    contact_id = Column(Integer, )

    def __repr__(self):
        return f'Group {self.screen_name} id {self.id}'

class Post(CustomBase):
    """Post model."""
    __inittablename__ = 'posts'
    __table_args__ = (PrimaryKeyConstraint('post_id', 'owner_id'),)

    id = Column(Integer, autoincrement=True, unique=True, index=True)
    post_id = Column(Integer, index=True)
    owner_id = Column(Integer, ForeignKey('groups.id'), index=True)
    date = Column(DateTime, comment='Publication timestamp in MSC tz')
    marked_as_ads = Column(Boolean, default=False)
    post_type = Column(String)
    text = Column(Text)
    likes_count = Column(Integer)
    repost_count = Column(Integer)
    views_count = Column(Integer)
    comment_count = Column(Integer)

    group = relationship('Group')

    def __repr__(self):
        return f'Post id {self.post_id}: {self.text[:31]}'

class Comment(CustomBase):
    __inittablename__ = 'comments'
    __table_args__ = (PrimaryKeyConstraint('id', 'owner_id'),)

    id = Column(Integer, autoincrement=True, index=True)
    from_id = Column(
        Integer, ForeignKey('users.id'), comment='ID of comment author'
    )
    post_id = Column(Integer, ForeignKey('posts.id'))
    owner_id = Column(
        Integer, ForeignKey('groups.id'), index=True,
        comment='ID of group feed with the comment'
    )
    date = Column(DateTime, comment='Publication timestamp in MSC tz')
    text = Column(Text)

    post = relationship(Post, primaryjoin=post_id == Post.post_id, foreign_keys=Post.post_id)
    author = relationship(User, primaryjoin=from_id == User.id, post_update=True)
    group = relationship('Group')

    def __repr__(self):
        return f'Comment id {self.id}: {self.text[:31]}'

class PostWord(CustomBase):
    __inittablename__ = 'posts_words'

    id = Column(Integer, autoincrement=True, index=True, primary_key=True)
    word = Column(String(length=255), )
    post_id = Column(Integer, ForeignKey('posts.id'))
    date = Column(Date, comment='Publication date of original post in MSC tz')
    post = relationship(Post, primaryjoin=post_id == Post.id, foreign_keys=Post.id)

try:
    CustomBase.metadata.create_all(db_engine, checkfirst=True)
except Exception as e:
    err = f'Got an error creating DB tables: {e}'
    print(err)
    logging.error(msg=err)
