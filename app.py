from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'  # ganti di produksi
db_path = os.path.join(os.path.dirname(__file__), 'kantingo.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Model Order
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nim = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    items = db.Column(db.Text, nullable=False)  # format plain text
    status = db.Column(db.String(20), nullable=False, default='queued')  # queued, preparing, ready, picked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'nim': self.nim,
            'name': self.name,
            'items': self.items,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }

# Initialize DB
@app.before_first_request
def create_tables():
    db.create_all()

# Helper: compute queue position for a given order id
def queue_position(order_id):
    order = Order.query.get(order_id)
    if not order:
        return None
    # orders still in queue = statuses queued or preparing (not ready/picked)
    earlier = Order.query.filter(
        Order.status.in_(['queued','preparing']),
        Order.created_at < order.created_at
    ).count()
    # position is earlier + 1 but if order already ready/picked -> position = 0 (not in queue)
    if order.status in ['ready','picked']:
        return 0
    return earlier + 1

# Route: home (mahasiswa)
@app.route('/')
def index():
    return render_template('index.html')

# Route: admin
@app.route('/admin')
def admin():
    return render_template('admin.html')

# API: place order
@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    nim = data.get('nim', '').strip()
    name = data.get('name', '').strip()
    items = data.get('items', '').strip()
    if not nim or not name or not items:
        return jsonify({'error': 'lengkapi nim, name, dan items'}), 400
    order = Order(nim=nim, name=name, items=items, status='queued')
    db.session.add(order)
    db.session.commit()

    # Emit event ke semua client: new_order
    socketio.emit('new_order', order.to_dict())
    # also emit queue_update
    emit_queue_update()
    return jsonify({'order': order.to_dict()}), 201

# API: get orders (optionally all or by order id)
@app.route('/api/orders', methods=['GET'])
def list_orders():
    status = request.args.get('status')
    query = Order.query
    if status:
        query = query.filter_by(status=status)
    orders = query.order_by(Order.created_at).all()
    return jsonify([o.to_dict() for o in orders])

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    o = Order.query.get_or_404(order_id)
    pos = queue_position(order_id)
    d = o.to_dict()
    d['position'] = pos
    return jsonify(d)

# API: change status (used by admin)
@app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
def update_status(order_id):
    o = Order.query.get_or_404(order_id)
    data = request.json
    new_status = data.get('status')
    if new_status not in ['queued','preparing','ready','picked']:
        return jsonify({'error': 'status tidak valid'}), 400
    o.status = new_status
    db.session.commit()
    socketio.emit('order_updated', o.to_dict())
    emit_queue_update()
    return jsonify(o.to_dict())

# Emit queue summary
def emit_queue_update():
    # count per status
    queued = Order.query.filter_by(status='queued').count()
    preparing = Order.query.filter_by(status='preparing').count()
    ready = Order.query.filter_by(status='ready').count()
    # send list of queued orders (ordered)
    queued_list = [o.to_dict() for o in Order.query.filter(Order.status.in_(['queued','preparing'])).order_by(Order.created_at).all()]
    socketio.emit('queue_update', {
        'queued': queued,
        'preparing': preparing,
        'ready': ready,
        'list': queued_list
    })

# Socket handlers for client connection
@socketio.on('connect')
def handle_connect():
    # Send initial queue state
    emit_queue_update()

if __name__ == '__main__':
    # Use eventlet server
    socketio.run(app, host='0.0.0.0', port=5000)
