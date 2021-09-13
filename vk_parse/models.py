"""Describe data models and their relations."""
import configparser
import logging

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey,
                        ForeignKeyConstraint, Index, Integer, MetaData,
                        PrimaryKeyConstraint, SmallInteger, String, Table,
                        Text, UniqueConstraint, create_engine, inspect)
from sqlalchemy.orm import (declarative_base, declared_attr, relationship,
                            sessionmaker)
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
user = config.get('database', 'user')
password = config.get('database', 'password')
host = config.get('database', 'host')
database = config.get('database', 'db')
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
        return cls.__intablename__


class User(CustomBase):
    __intablename__ = 'users'

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
    __intablename__ = 'groups'

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
    __intablename__ = 'posts'
    __table_args__ = (PrimaryKeyConstraint('post_id', 'owner_id'), )

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
        return f'Post id {self.id}: {self.text[:31]}'


class Comment(CustomBase):
    __intablename__ = 'comments'
    __table_args__ = (PrimaryKeyConstraint('id', 'owner_id'),)

    id = Column(Integer, autoincrement=True, index=True)
    from_id = Column(
        Integer, ForeignKey('users.id') ,comment='ID of comment author'
    )
    post_id = Column(Integer, ForeignKey('posts.post_id'))
    owner_id = Column(
        Integer, ForeignKey('groups.id'), index=True,
        comment='ID of group feed with the comment'
    )
    date = Column(DateTime, comment='Publication timestamp in MSC tz')
    text = Column(Text)
    #
    # ForeignKeyConstraint(
    #     ('post_id', 'owner_id'),
    #     ['posts.post_id', 'posts.owner_id'],
    #     name='fk_post_post_id_constraint'
    # )

    post = relationship(Post, primaryjoin=post_id==Post.post_id,foreign_keys=Post.post_id)
    author = relationship(User, primaryjoin=from_id==User.id,post_update=True)
    group = relationship('Group')

    def __repr__(self):
        return f'Comment id {self.id}: {self.text[:31]}'

try:
    Base.metadata.create_all(db_engine)
except Exception as e:
    err = f'Got an error creating DB tables: {e}'
    print(err)
    logging.error(msg=err)
