from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, PoolForm, GroupPoolForm, HydrochemistryForm, FishTypeForm, \
                  FishInventoryForm, FishBoningForm, FeedForm, FeedTypeForm,\
                  FishMovementForm, PoolSelectionForm, HydrochemistryGraphForm, HydrochemistryFilterForm
from models import db, User, Pool, GroupPool, Hydrochemistry, FishType,\
                   FishInventory, FishBoning, FeedType, Feed, FishMovement, group_pool_pool
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

import plotly.graph_objs as go
import plotly.offline as pyo

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Для доступа к данным необходимо войти в систему.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_tables():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin', method='pbkdf2:sha256'))
        db.session.add(admin)
        db.session.commit()

# Add datetimeformat filter
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    return datetime.fromtimestamp(value).strftime(format)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/hydrochemistry', methods=['GET', 'POST'])
@login_required
def hydrochemistry():
    filter_form = HydrochemistryFilterForm()
    query = Hydrochemistry.query

    if filter_form.validate_on_submit():
        start_date = int(filter_form.start_date.data.timestamp())
        end_date = int(filter_form.end_date.data.timestamp())
        query = query.filter(Hydrochemistry.hydrochem_date >= start_date, Hydrochemistry.hydrochem_date <= end_date)

        # Обработка сортировки
    sort_by = request.args.get('sort_by', 'hydrochem_date')  # По умолчанию сортируем по дате
    reverse = bool(request.args.get('reverse'))  # Если параметр reverse есть в URL, сортируем в обратном порядке

    # Сортировка данных
    if sort_by in ['hydrochem_date', 'doxy', 'temperature', 'ph', 'no2', 'no3', 'nh4', 'po4', 'salinity',
                   'illumination']:
        sort_attr = getattr(Hydrochemistry, sort_by)
        if reverse:
            query = query.order_by(sort_attr.desc())
        else:
            query = query.order_by(sort_attr)

    records = query.all()
    return render_template('hydrochemistry.html', records=records, filter_form=filter_form)

@app.route('/hydrochemistry/new', methods=['GET', 'POST'])
@login_required
def new_hydrochemistry():
    form = HydrochemistryForm()
    if form.validate_on_submit():
        new_group_id = Hydrochemistry.query.filter_by(group_pool_id=form.group_pool_id.data, hydrochem_date=int(form.hydrochem_date.data.timestamp())).first()
        if new_group_id:
            flash('Басейн с таким названием уже существует для текущей даты', 'danger')
        else:
            record = Hydrochemistry(
                group_pool_id=form.group_pool_id.data,
                hydrochem_date=int(form.hydrochem_date.data.timestamp()),
                doxy=(form.doxy.data),
                temperature=(form.temperature.data),
                ph=(form.ph.data),
                no2=(form.no2.data),
                no3=(form.no3.data),
                nh4=(form.nh4.data),
                po4=(form.po4.data),
                salinity=(form.salinity.data),
                illumination=(form.illumination.data)
            )
            db.session.add(record)
            db.session.commit()
            flash('Запись успешно добавленна', 'success')
            return redirect(url_for('hydrochemistry'))
    return render_template('edit_hydrochemistry.html', form=form)

@app.route('/hydrochemistry/edit/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit_hydrochemistry(record_id):
    record = Hydrochemistry.query.get_or_404(record_id)
    form = HydrochemistryForm(obj=record)
    # Преобразуем дату из UNIX timestamp в datetime, если форма инициализируется данными из записи
    form.hydrochem_date.data = datetime.fromtimestamp(record.hydrochem_date)

    if form.validate_on_submit():
        record.group_pool_id = form.group_pool_id.data
        record.hydrochem_date = int(form.hydrochem_date.data.timestamp())
        record.doxy = (form.doxy.data)
        record.temperature = (form.temperature.data)
        record.ph = (form.ph.data)
        record.no2 = (form.no2.data)
        record.no3 = (form.no3.data)
        record.nh4 = (form.nh4.data)
        record.po4 = (form.po4.data)
        record.salinity = (form.salinity.data)
        record.illumination = (form.illumination.data)
        db.session.commit()
        flash('Запись гидрохимии успешно обновлена', 'success')
        return redirect(url_for('hydrochemistry'))
    return render_template('edit_hydrochemistry.html', form=form, record=record)

@app.route('/hydrochemistry/delete/<int:record_id>', methods=['POST'])
@login_required
def delete_hydrochemistry(record_id):
    record = Hydrochemistry.query.get_or_404(record_id)
    try:
        db.session.delete(record)
        db.session.commit()
        flash('Запись гидрохимии успешно удалена', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Невозможно удалить запись, так как данные используются', 'danger')
    return redirect(url_for('hydrochemistry'))


@app.route('/pools', methods=['GET', 'POST'])
@login_required
def pools():
    pool_form = PoolForm()
    group_pool_form = GroupPoolForm()
    pool_selection_form = PoolSelectionForm()
    pools = Pool.query.all()
    group_pools = GroupPool.query.all()
    latest_hydrochemistry = None

    if pool_selection_form.validate_on_submit():
        selected_pool_id = pool_selection_form.pool_id.data
        latest_hydrochemistry = Hydrochemistry.query\
            .join(GroupPool)\
            .join(group_pool_pool)\
            .join(Pool)\
            .filter(Pool.id == selected_pool_id)\
            .order_by(Hydrochemistry.hydrochem_date.desc())\
            .first()

    return render_template('pools.html', pools=pools, group_pools=group_pools,
                           pool_form=pool_form, group_pool_form=group_pool_form,
                           pool_selection_form=pool_selection_form, latest_hydrochemistry=latest_hydrochemistry)

@app.route('/pool/new', methods=['GET', 'POST'])
@login_required
def new_pool():
    form = PoolForm()
    if form.validate_on_submit():
        pool = Pool(name=form.name.data)
        db.session.add(pool)
        db.session.commit()
        flash('Бассейн успешно добавленн', 'success')
        return redirect(url_for('pools'))
    return render_template('edit_pool.html', form=form)

@app.route('/pool/<int:pool_id>', methods=['GET', 'POST'])
@login_required
def edit_pool(pool_id):
    pool = Pool.query.get_or_404(pool_id)
    form = PoolForm(obj=pool)
    if form.validate_on_submit():
        form.populate_obj(pool)
        db.session.commit()
        flash('Бассейн успешно обновлен', 'success')
        return redirect(url_for('pools'))
    return render_template('edit_pool.html', form=form, pool=pool)

@app.route('/pool/delete/<int:pool_id>', methods=['POST'])
@login_required
def delete_pool(pool_id):
    try:
        pool = Pool.query.get_or_404(pool_id)
        db.session.delete(pool)
        db.session.commit()
        flash('Бассейн успешно удален', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Невозможно удалить запись, так как данные используются', 'danger')
    return redirect(url_for('pools'))

@app.route('/group_pool/new', methods=['GET', 'POST'])
@login_required
def new_group_pool():
    form = GroupPoolForm()
    if form.validate_on_submit():
        selected_pools_ids = form.pools.data
        group_pool = GroupPool(name=form.name.data)
        for pool_id in selected_pools_ids:
            pool = Pool.query.get(pool_id)
            group_pool.pools.append(pool)
        db.session.add(group_pool)
        db.session.commit()
        flash('Групповой бассейн успешно добавленн', 'success')
        return redirect(url_for('pools'))
    return render_template('edit_group_pool.html', form=form)

@app.route('/group_pool/<int:group_pool_id>', methods=['GET', 'POST'])
@login_required
def edit_group_pool(group_pool_id):
    group_pool = GroupPool.query.get_or_404(group_pool_id)
    form = GroupPoolForm(obj=group_pool)
    if form.validate_on_submit():
        selected_pools_ids = form.pools.data
        group_pool.name = form.name.data
        group_pool.pools = [Pool.query.get(pool_id) for pool_id in selected_pools_ids]
        db.session.commit()
        flash('Групповой бассейн успешно обновлен', 'success')
        return redirect(url_for('pools'))
    form.pools.data = [pool.id for pool in group_pool.pools]
    return render_template('edit_group_pool.html', form=form, group_pool=group_pool)

@app.route('/group_pool/delete/<int:group_pool_id>', methods=['POST'])
@login_required
def delete_group_pool(group_pool_id):
    try:
        group_pool = GroupPool.query.get_or_404(group_pool_id)
        db.session.delete(group_pool)
        db.session.commit()
        flash('Групповой бассейн успешно удален', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Невозможно удалить запись, так как данные используются', 'danger')
    return redirect(url_for('pools'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    return render_template('login.html', form=form)

@app.route('/fish')
@login_required
def fish():
    fish_types = FishType.query.all()
    return render_template('fish.html', fish_types=fish_types)

@app.route('/fish_type/new', methods=['GET', 'POST'])
@login_required
def new_fish_type():
    form = FishTypeForm()
    if form.validate_on_submit():
        fish_type = FishType(name=form.name.data)
        db.session.add(fish_type)
        db.session.commit()
        flash('Вид рыбы успешно добавлен', 'success')
        return redirect(url_for('fish'))
    return render_template('edit_fish_type.html', form=form)

@app.route('/fish_type/delete/<int:fish_type_id>', methods=['POST'])
@login_required
def delete_fish_type(fish_type_id):
    try:
        fish_type = FishType.query.get_or_404(fish_type_id)
        db.session.delete(fish_type)
        db.session.commit()
        flash('Вид рыбы успешно удален', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Невозможно удалить запись, так как данные используются', 'danger')
    return redirect(url_for('fish'))

@app.route('/fish_type/edit/<int:fish_type_id>', methods=['GET', 'POST'])
@login_required
def edit_fish_type(fish_type_id):
    fish_type = FishType.query.get_or_404(fish_type_id)
    form = FishTypeForm(obj=fish_type)

    if form.validate_on_submit():
        fish_type.name = form.name.data
        db.session.commit()
        flash('Вид рыбы успешно обновлен', 'success')
        return redirect(url_for('fish'))
    return render_template('edit_fish_type.html', form=form)

@app.route('/inventory')
@login_required
def inventory():
    fish_inventories = FishInventory.query.all()
    fish_bonings = FishBoning.query.all()
    return render_template('inventory.html', fish_inventories=fish_inventories, fish_bonings=fish_bonings, title='Инвентаризация')

@app.route('/fish_inventory/new', methods=['GET', 'POST'])
@login_required
def new_fish_inventory():
    form = FishInventoryForm()
    form.pool_id.choices = [(pool.id, pool.name) for pool in Pool.query.all()]
    form.fish_type_id.choices = [(fish_type.id, fish_type.name) for fish_type in FishType.query.all()]
    if form.validate_on_submit():
        fish_inventory = FishInventory(
            control_date=int(form.control_date.data.timestamp()),
            pool_id=form.pool_id.data,
            fish_type_id=form.fish_type_id.data,
            control_desc=form.control_desc.data
        )
        db.session.add(fish_inventory)
        db.session.commit()
        flash('Запись инвентаря успешно добавлена', 'success')
        return redirect(url_for('inventory'))
    return render_template('edit_fish_inventory.html', form=form)


@app.route('/fish_inventory/edit/<int:inventory_id>', methods=['GET', 'POST'])
@login_required
def edit_fish_inventory(inventory_id):
    fish_inventory = FishInventory.query.get_or_404(inventory_id)
    form = FishInventoryForm(obj=fish_inventory)
    form.pool_id.choices = [(pool.id, pool.name) for pool in Pool.query.all()]
    form.fish_type_id.choices = [(fish_type.id, fish_type.name) for fish_type in FishType.query.all()]

    # Преобразуем дату из UNIX timestamp в datetime, если форма инициализируется данными из записи
    if request.method == 'GET':
        form.control_date.data = datetime.fromtimestamp(fish_inventory.control_date)

    if form.validate_on_submit():
        fish_inventory.control_date = int(form.control_date.data.timestamp())
        fish_inventory.pool_id = form.pool_id.data
        fish_inventory.fish_type_id = form.fish_type_id.data
        fish_inventory.control_desc = form.control_desc.data
        db.session.commit()
        flash('Запись инвентаря успешно обновлена', 'success')
        return redirect(url_for('inventory'))
    return render_template('edit_fish_inventory.html', form=form, fish_inventory=fish_inventory)


@app.route('/fish_inventory/delete/<int:inventory_id>', methods=['POST'])
@login_required
def delete_fish_inventory(inventory_id):
    try:
        fish_inventory = FishInventory.query.get_or_404(inventory_id)
        db.session.delete(fish_inventory)
        db.session.commit()
        flash('Запись инвентаря успешно удалена', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Невозможно удалить запись, так как данные используются', 'danger')
    return redirect(url_for('inventory'))


@app.route('/fish_boning/new', methods=['GET', 'POST'])
@login_required
def new_fish_boning():
    form = FishBoningForm()
    form.fish_inventory_id.choices = [(fish_inventory.id, f"{fish_inventory.pool.name} - {datetime.fromtimestamp(fish_inventory.control_date).strftime('%Y-%m-%d %H:%M:%S')}") for fish_inventory in FishInventory.query.all()]
    if form.validate_on_submit():
        fish_boning = FishBoning(
            fish_inventory_id=form.fish_inventory_id.data,
            fish_number=form.fish_number.data,
            fish_biomass=form.fish_biomass.data,
            fish_comment=form.fish_comment.data
        )
        db.session.add(fish_boning)
        db.session.commit()
        flash('Запись о бонитировки успешно добавлена', 'success')
        return redirect(url_for('inventory'))
    return render_template('edit_fish_boning.html', form=form)

@app.route('/fish_boning/edit/<int:boning_id>', methods=['GET', 'POST'])
@login_required
def edit_fish_boning(boning_id):
    fish_boning = FishBoning.query.get_or_404(boning_id)
    form = FishBoningForm(obj=fish_boning)
    form.fish_inventory_id.choices = [(fi.id, f"{fi.pool.name} - {datetime.fromtimestamp(fi.control_date).strftime('%Y-%m-%d %H:%M:%S')}") for fi in FishInventory.query.all()]

    if form.validate_on_submit():
        fish_boning.fish_inventory_id = form.fish_inventory_id.data
        fish_boning.fish_number = form.fish_number.data
        fish_boning.fish_biomass = form.fish_biomass.data
        fish_boning.fish_comment = form.fish_comment.data
        db.session.commit()
        flash('Запись о бонитировки успешно обновлена', 'success')
        return redirect(url_for('inventory'))
    return render_template('edit_fish_boning.html', form=form, fish_boning=fish_boning)

@app.route('/fish_boning/delete/<int:boning_id>', methods=['POST'])
@login_required
def delete_fish_boning(boning_id):
    try:
        fish_boning = FishBoning.query.get_or_404(boning_id)
        db.session.delete(fish_boning)
        db.session.commit()
        flash('Запись о бонитировки успешно удалена', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Невозможно удалить запись, так как данные используются', 'danger')
    return redirect(url_for('inventory'))

@app.route('/feeding')
@login_required
def feeding():
    feed_types = FeedType.query.all()
    feeds = Feed.query.all()
    return render_template('feeding.html', feed_types=feed_types, feeds=feeds)

@app.route('/feed_type/new', methods=['GET', 'POST'])
@login_required
def new_feed_type():
    form = FeedTypeForm()
    if form.validate_on_submit():
        feed_type = FeedType(name=form.name.data, unit=form.unit.data)
        db.session.add(feed_type)
        db.session.commit()
        flash('Тип корма успешно добавлен', 'success')
        return redirect(url_for('feeding'))
    return render_template('edit_feed_type.html', form=form)

@app.route('/feed/new', methods=['GET', 'POST'])
@login_required
def new_feed():
    form = FeedForm()
    form.pool_id.choices = [(pool.id, pool.name) for pool in Pool.query.all()]
    form.feed_type_id.choices = [(feed_type.id, feed_type.name) for feed_type in FeedType.query.all()]
    if form.validate_on_submit():
        feed = Feed(
            pool_id=form.pool_id.data,
            feed_date=int(form.feed_date.data.timestamp()),
            feed_type_id=form.feed_type_id.data,
            feed_value=form.feed_value.data,
            feed_desc=form.feed_desc.data
        )
        db.session.add(feed)
        db.session.commit()
        flash('Запись о кормлении успешно добавлена', 'success')
        return redirect(url_for('feeding'))
    return render_template('edit_feed.html', form=form)

@app.route('/feed/edit/<int:feed_id>', methods=['GET', 'POST'])
@login_required
def edit_feed(feed_id):
    feed = Feed.query.get_or_404(feed_id)
    form = FeedForm(obj=feed)
    # Преобразуем дату из UNIX timestamp в datetime, если форма инициализируется данными из записи
    form.feed_date.data = datetime.fromtimestamp(feed.feed_date)
    form.pool_id.choices = [(pool.id, pool.name) for pool in Pool.query.all()]
    form.feed_type_id.choices = [(feed_type.id, feed_type.name) for feed_type in FeedType.query.all()]

    if form.validate_on_submit():
        feed.pool_id = form.pool_id.data
        feed.feed_date = int(form.feed_date.data.timestamp())
        feed.feed_type_id = form.feed_type_id.data
        feed.feed_value = form.feed_value.data
        feed.feed_desc = form.feed_desc.data
        db.session.commit()
        flash('Запись о кормлении успешно обновлена', 'success')
        return redirect(url_for('feeding'))
    return render_template('edit_feed.html', form=form, feed=feed)

@app.route('/feed/delete/<int:feed_id>', methods=['POST'])
@login_required
def delete_feed(feed_id):
    try:
        feed = Feed.query.get_or_404(feed_id)
        db.session.delete(feed)
        db.session.commit()
        flash('Запись о кормлении успешно удалена', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Невозможно удалить запись, так как данные используются', 'danger')
    return redirect(url_for('feeding'))


@app.route('/feed_type/edit/<int:feed_type_id>', methods=['GET', 'POST'])
@login_required
def edit_feed_type(feed_type_id):
    feed_type = FeedType.query.get_or_404(feed_type_id)
    form = FeedTypeForm(obj=feed_type)

    if form.validate_on_submit():
        feed_type.name = form.name.data
        feed_type.unit = form.unit.data
        db.session.commit()
        flash('Тип корма успешно добавлен', 'success')
        return redirect(url_for('feeding'))
    return render_template('edit_feed_type.html', form=form, feed_type=feed_type)

@app.route('/feed_type/delete/<int:feed_type_id>', methods=['POST'])
@login_required
def delete_feed_type(feed_type_id):
    try:
        feed_type = FeedType.query.get_or_404(feed_type_id)
        db.session.delete(feed_type)
        db.session.commit()
        flash('Тип корма успешно удален', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Невозможно удалить запись, так как данные используются', 'danger')
    return redirect(url_for('feeding'))

@app.route('/movement')
@login_required
def movement():
    movements = FishMovement.query.all()
    return render_template('movement.html', movements=movements)

@app.route('/fish_movement/new', methods=['GET', 'POST'])
@login_required
def new_fish_movement():
    form = FishMovementForm()
    form.pool_id_from.choices = [(pool.id, pool.name) for pool in Pool.query.all()]
    form.pool_id_to.choices = [(pool.id, pool.name) for pool in Pool.query.all()]
    form.fish_type_id.choices = [(fish_type.id, fish_type.name) for fish_type in FishType.query.all()]
    if form.validate_on_submit():
        if form.pool_id_from.data == form.pool_id_to.data:
            flash('Басейны совпадают', 'danger')
        else:
            fish_movement = FishMovement(
                pool_id_from=form.pool_id_from.data,
                pool_id_to=form.pool_id_to.data,
                fish_type_id=form.fish_type_id.data,
                movement_date=int(form.movement_date.data.timestamp()),
                fish_biomass=form.fish_biomass.data,
                movement_reason=form.movement_reason.data,
                movement_desc=form.movement_desc.data
            )
            db.session.add(fish_movement)
            db.session.commit()
            flash('Запись о перемещении успешна добавлена', 'success')
            return redirect(url_for('movement'))
    return render_template('edit_fish_movement.html', form=form)

@app.route('/fish_movement/edit/<int:movement_id>', methods=['GET', 'POST'])
@login_required
def edit_fish_movement(movement_id):
    fish_movement = FishMovement.query.get_or_404(movement_id)
    form = FishMovementForm(obj=fish_movement)
    form.pool_id_from.choices = [(pool.id, pool.name) for pool in Pool.query.all()]
    form.pool_id_to.choices = [(pool.id, pool.name) for pool in Pool.query.all()]
    form.fish_type_id.choices = [(fish_type.id, fish_type.name) for fish_type in FishType.query.all()]

    # Преобразуем дату из UNIX timestamp в datetime, если форма инициализируется данными из записи
    if request.method == 'GET':
        form.movement_date.data = datetime.fromtimestamp(fish_movement.movement_date)

    if form.validate_on_submit():
        if form.pool_id_from.data == form.pool_id_to.data:
            flash('Бассейны совпадают', 'danger')
        else:
            fish_movement.pool_id_from = form.pool_id_from.data
            fish_movement.pool_id_to = form.pool_id_to.data
            fish_movement.fish_type_id = form.fish_type_id.data
            fish_movement.movement_date = int(form.movement_date.data.timestamp())
            fish_movement.fish_biomass = form.fish_biomass.data
            fish_movement.movement_reason = form.movement_reason.data
            fish_movement.movement_desc = form.movement_desc.data

            db.session.commit()
            flash('Запись о перемещении успешна обновлена', 'success')
            return redirect(url_for('movement'))
    return render_template('edit_fish_movement.html', form=form, movement=fish_movement)

@app.route('/fish_movement/delete/<int:movement_id>', methods=['POST'])
@login_required
def delete_fish_movement(movement_id):
    try:
        fish_movement = FishMovement.query.get_or_404(movement_id)
        db.session.delete(fish_movement)
        db.session.commit()
        flash('Запись о перемещении успешна удалена', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Невозможно удалить запись, так как данные используются', 'danger')
    return redirect(url_for('movement'))

@app.route('/fish_composition', methods=['GET'])
@login_required
def fish_composition():
    # Получение последней инвентаризации для каждого бассейна
    subquery = db.session.query(
        FishInventory.pool_id,
        FishInventory.fish_type_id,
        db.func.max(FishInventory.control_date).label('latest_date')
    ).group_by(FishInventory.pool_id, FishInventory.fish_type_id).subquery()

    latest_inventories = db.session.query(FishInventory).join(
        subquery,
        db.and_(
            FishInventory.pool_id == subquery.c.pool_id,
            FishInventory.fish_type_id == subquery.c.fish_type_id,
            FishInventory.control_date == subquery.c.latest_date
        )
    ).all()

    fish_data = {}

    for inventory in latest_inventories:
        pool_id = inventory.pool_id
        fish_type_id = inventory.fish_type_id
        fish_type_name = inventory.fish_type.name

        bonings = FishBoning.query.filter_by(fish_inventory_id=inventory.id).all()
        total_count = sum(boning.fish_number for boning in bonings)
        total_mass = sum(boning.fish_biomass for boning in bonings)

        if fish_type_name not in fish_data:
            fish_data[fish_type_name] = {
                'total_count': 0,
                'total_mass': 0,
                'pools': set()
            }

        fish_data[fish_type_name]['total_count'] += total_count
        fish_data[fish_type_name]['total_mass'] += total_mass
        pool_name = Pool.query.filter_by(id=pool_id).first()
        fish_data[fish_type_name]['pools'].add(pool_name.name)

    return render_template('fish_composition.html', fish_data=fish_data, enumerate=enumerate, map=map)

@app.route('/hydrochemistry/generate', methods=['GET', 'POST'])
@login_required
def generate_journal():
    group_pools = GroupPool.query.all()
    current_date = datetime.utcnow()
    record_add = 0
    if request.method == 'POST':
        for gp in group_pools:
            if request.form.get(f'select_{gp.id}'):
                date_str = request.form.get(f'date_{gp.id}')
                try:
                    datetime_obj = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash(f'Некорректный формат даты для группового бассейна {gp.name}', 'danger')
                    continue

                def get_float_value(field_name):
                    value = request.form.get(field_name)
                    return float(value) if value else None

                record = Hydrochemistry(
                    group_pool_id=gp.id,
                    hydrochem_date=int(datetime_obj.timestamp()),
                    doxy=get_float_value(f'doxy_{gp.id}'),
                    temperature=get_float_value(f'temperature_{gp.id}'),
                    ph=get_float_value(f'ph_{gp.id}'),
                    no2=get_float_value(f'no2_{gp.id}'),
                    no3=get_float_value(f'no3_{gp.id}'),
                    nh4=get_float_value(f'nh4_{gp.id}'),
                    po4=get_float_value(f'po4_{gp.id}'),
                    salinity=get_float_value(f'salinity_{gp.id}'),
                    illumination=get_float_value(f'illumination_{gp.id}')
                )
                db.session.add(record)
                record_add = record_add + 1
        db.session.commit()
        if record_add == 0:
            flash('Ни одна запись не добавлена', 'danger')
        else:
            flash('Журнал успешно создан', 'success')
        return redirect(url_for('hydrochemistry'))
    return render_template('generate_journal.html', group_pools=group_pools, current_date=current_date)


@app.route('/plot_graph', methods=['GET', 'POST'])
@login_required
def plot_graph():
    form = HydrochemistryGraphForm()
    plot = None
    parameter_display_name = None

    if form.validate_on_submit():
        parameter = form.parameter.data
        parameter_display_name = dict(form.parameter.choices).get(parameter)
        start_date = form.start_date.data
        end_date = form.end_date.data

        # Convert dates to Unix timestamp
        start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        end_timestamp = int(datetime.combine(end_date, datetime.min.time()).timestamp())

        data = Hydrochemistry.query.filter(Hydrochemistry.hydrochem_date.between(start_timestamp, end_timestamp)).all()

        if data:
            plot = create_plot(data, parameter, parameter_display_name)

    return render_template('plot_graph.html', form=form, plot=plot, parameter_display_name=parameter_display_name)


def create_plot(data, parameter, parameter_display_name):
    traces = []
    pool_ids = {record.group_pool_id for record in data}
    pools = {pool.id: pool.name for pool in GroupPool.query.filter(GroupPool.id.in_(pool_ids)).all()}

    for pool_id in pools:
        pool_data = [record for record in data if record.group_pool_id == pool_id]
        pool_data.sort(key=lambda x: x.hydrochem_date)
        x = [datetime.fromtimestamp(record.hydrochem_date) for record in pool_data]
        y = [getattr(record, parameter) for record in pool_data]

        traces.append(go.Scatter(x=x, y=y, mode='lines', name=pools[pool_id]))

    layout = go.Layout(title=f'{parameter_display_name} по времени', xaxis=dict(title='Время'),
                       yaxis=dict(title=parameter_display_name))
    fig = go.Figure(data=traces, layout=layout)

    return pyo.plot(fig, output_type='div')

if __name__ == '__main__':
    with app.app_context():
        create_tables()
    app.run(debug=True)
