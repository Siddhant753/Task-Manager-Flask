from flask import Flask, render_template, request, redirect, session
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask import url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from datetime import datetime
import bcrypt
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.secret_key = 'Task_Manager_Project'

class Todo(db.Model):
    srno = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(200), nullable = False)
    desc = db.Column(db.String(500), nullable = False)
    date_created = db.Column(db.DateTime, default = datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable = False)

    def __repr__(self):
        return f"{self.srno} - {self.title}"
    
class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(100), nullable = False)
    email = db.Column(db.String(100), unique = True)
    password = db.Column(db.String(100), nullable = False)
    is_admin = db.Column(db.Boolean, default = False)

    todos = db.relationship('Todo', backref = 'user', lazy = True)

    def __init__(self, username,email, password):
        self.username = username
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))
    
class Reviews(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable = False)
    content = db.Column(db.Text, nullable = False)
    date_created = db.Column(db.DateTime, default = datetime.now)

    user = db.relationship('User', backref = db.backref('reviews', lazy = True))
    
with app.app_context():
    db.create_all()

def get_current_user():
    email = session.get('email')
    if not email:
        return None
    return User.query.filter_by(email = email).first()

@app.route('/', methods=['POST', 'GET'])
def hello_world():
    user = None
    alltodo = []

    if 'email' in session:
        user = User.query.filter_by(email=session['email']).first()
        if user:
            alltodo = Todo.query.filter_by(user_id=user.id).all()

    if request.method == 'POST':
        title = request.form.get('title')
        desc = request.form.get('desc')

        if not user:
            # Save pending task in session
            session['pending_task'] = {'title': title, 'desc': desc}
            session['redirect_after_login'] = '/'  # optional
            return redirect('/login?next=/')

        # Thsi save task normally if logged in
        todo = Todo(title=title, desc=desc, user_id=user.id)
        db.session.add(todo)
        db.session.commit()
        return redirect('/')

    return render_template('index.html', alltodo=alltodo, username=session.get('username'))


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/delete/<int:srno>')
def delete(srno):
    user = get_current_user()
    if not user:
        return redirect('/login?next=/')
    
    todo = Todo.query.filter_by(srno = srno, user_id = user.id).first_or_404()
    db.session.delete(todo)
    db.session.commit()
    return redirect('/')

@app.route('/update/<int:srno>', methods = ['GET', 'POST'])
def update(srno):
    user = get_current_user()
    if not user:
        return redirect('/login?next=/')
    
    if request.method == 'POST':
        title = request.form.get('title')
        desc = request.form.get('desc')
        todo = Todo.query.filter_by(srno = srno, user_id = user.id).first_or_404()
        todo.title = title
        todo.desc = desc
        db.session.add(todo)
        db.session.commit()
        return redirect('/')
    todo = Todo.query.filter_by(srno = srno, user_id = user.id).first_or_404()
    return render_template('update.html', todo = todo)

@app.route('/search')
def search():
    query = (request.args.get('query') or '').strip()
    user = get_current_user()
    # Non user will not see any task in search
    if not user:
        return render_template(
            'search.html',
            results = [],
            query = query,
            username = session.get('username'),
            error = 'Login to search your tasks'
            )
    results = []

    if query:
        results = Todo.query.filter(Todo.user_id == user.id, or_(Todo.title.like(f"%{query}%"),Todo.desc.like(f"%{query}%"))).order_by(Todo.date_created.desc()).all()
    
    return render_template('search.html', results= results, query = query, username = session.get('username'))

@app.route('/register', methods = ['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # if user already exists
        existing_user = User.query.filter_by(email = email).first()
        if existing_user:
            return render_template('register.html', error = "This email is already registered.")

        # if password != confirm password
        if password != confirm_password:
            return render_template('register.html', error = "Passwords do not match.")
        

        new_user = User(username = username, email = email, password = password)
        db.session.add(new_user)
        db.session.commit()
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session['username'] = user.username
            session['email'] = user.email

            # Save pending task if exists
            if 'pending_task' in session:
                pending = session.pop('pending_task')
                todo = Todo(title=pending['title'], desc=pending['desc'], user_id=user.id)
                db.session.add(todo)
                db.session.commit()

            return redirect(session.pop('redirect_after_login', '/'))

        else:
            return render_template('login.html', error="Invalid User")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/reviews', methods = ['POST', 'GET'])
def reviews():
    user = get_current_user()

    if request.method == 'POST':
        if not user:
            return redirect('/login?next=/reviews')

        content = request.form.get('content')
        if content.strip():
            new_review = Reviews(user_id = user.id, content = content)
            db.session.add(new_review)
            db.session.commit()
            return redirect('/reviews')
        
    all_reviews = Reviews.query.order_by(Reviews.date_created.desc()).all()
    return render_template('reviews.html', reviews = all_reviews, username = user.username if user else None)

class SecureModelView(ModelView):
    def is_accessible(self):
        user = get_current_user()
        return user is not None and user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next = request.url))
    
admin = Admin(app, name = 'Admin Panel', template_mode = 'bootstrap4')

admin.add_view(SecureModelView(User, db.session))
admin.add_view(SecureModelView(Reviews, db.session))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)