from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Pool(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class GroupPool(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    pools = db.relationship('Pool', secondary='group_pool_pool', backref='group_pools')

group_pool_pool = db.Table('group_pool_pool',
    db.Column('group_pool_id', db.Integer, db.ForeignKey('group_pool.id'), primary_key=True),
    db.Column('pool_id', db.Integer, db.ForeignKey('pool.id'), primary_key=True)
)

class Hydrochemistry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_pool_id = db.Column(db.Integer, db.ForeignKey('group_pool.id'), nullable=False)
    hydrochem_date = db.Column(db.Integer, nullable=False)
    doxy = db.Column(db.Float, nullable=True)
    temperature = db.Column(db.Float, nullable=True)
    ph = db.Column(db.Float, nullable=True)
    no2 = db.Column(db.Float, nullable=True)
    no3 = db.Column(db.Float, nullable=True)
    nh4 = db.Column(db.Float, nullable=True)
    po4 = db.Column(db.Float, nullable=True)
    salinity = db.Column(db.Float, nullable=True)
    illumination = db.Column(db.Float, nullable=True)

    group_pool = db.relationship('GroupPool', backref='hydrochemistry_records')

class FishType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class FishInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    control_date = db.Column(db.Integer, nullable=False)
    pool_id = db.Column(db.Integer, db.ForeignKey('pool.id'), nullable=False)
    fish_type_id = db.Column(db.Integer, db.ForeignKey('fish_type.id'), nullable=False)
    control_desc = db.Column(db.Text, nullable=True)
    pool = db.relationship('Pool', backref=db.backref('fish_inventories', lazy=True))
    fish_type = db.relationship('FishType', backref=db.backref('fish_inventories', lazy=True))

class FishBoning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fish_inventory_id = db.Column(db.Integer, db.ForeignKey('fish_inventory.id'), nullable=False)
    fish_number = db.Column(db.Integer, nullable=False)
    fish_biomass = db.Column(db.Float, nullable=False)
    fish_comment = db.Column(db.Text, nullable=True)
    fish_inventory = db.relationship('FishInventory', backref=db.backref('fish_bonings', lazy=True))

class FeedType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(50), nullable=False)

class Feed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pool_id = db.Column(db.Integer, db.ForeignKey('pool.id'), nullable=False)
    feed_date = db.Column(db.Integer, nullable=False)
    feed_type_id = db.Column(db.Integer, db.ForeignKey('feed_type.id'), nullable=False)
    feed_value = db.Column(db.Float, nullable=False)
    feed_desc = db.Column(db.Text, nullable=True)
    pool = db.relationship('Pool', backref=db.backref('feeds', lazy=True))
    feed_type = db.relationship('FeedType', backref=db.backref('feeds', lazy=True))

class FishMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pool_id_from = db.Column(db.Integer, db.ForeignKey('pool.id'), nullable=True)
    pool_id_to = db.Column(db.Integer, db.ForeignKey('pool.id'), nullable=True)
    fish_type_id = db.Column(db.Integer, db.ForeignKey('fish_type.id'), nullable=False)
    movement_date = db.Column(db.Integer, nullable=False)
    fish_biomass = db.Column(db.Float, nullable=False)
    movement_reason = db.Column(db.Text, nullable=True)
    movement_desc = db.Column(db.Text, nullable=True)
    pool_from = db.relationship('Pool', foreign_keys=[pool_id_from], backref=db.backref('movements_from', lazy=True))
    pool_to = db.relationship('Pool', foreign_keys=[pool_id_to], backref=db.backref('movements_to', lazy=True))
    fish_type = db.relationship('FishType', backref=db.backref('movements', lazy=True))
