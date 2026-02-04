from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'secret_key_for_sessions'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

db = SQLAlchemy(app)

# ================== Models ==================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='submitter')

class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    image = db.Column(db.String(100))
    votes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    submitter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='idea', lazy=True, cascade="all, delete")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    idea_id = db.Column(db.Integer, db.ForeignKey('idea.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# ================== اللغة ==================
@app.before_request
def set_language():
    g.lang = session.get('lang', 'ar')

@app.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['ar','en']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

def _(ar_text, en_text):
    return en_text if g.get('lang') == 'en' else ar_text

@app.context_processor
def inject_functions():
    return dict(_=_)

# ================== Routes ==================
@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        if 'user_id' not in session:
            flash(_('يجب تسجيل الدخول','Login required'))
            return redirect(url_for('login'))

        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        image_file = request.files.get('image')

        filename = None
        if image_file and image_file.filename:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            filename = image_file.filename
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_idea = Idea(title=title, description=description, category=category,
                        image=filename, submitter_id=session['user_id'])
        db.session.add(new_idea)
        db.session.commit()
        flash(_('تمت إضافة الفكرة!','Idea added!'))
        return redirect(url_for('index'))

    ideas = Idea.query.order_by(Idea.id.desc()).all()
    return render_template('index.html', ideas=ideas)

@app.route('/delete_idea/<int:idea_id>', methods=['POST'])
def delete_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    if 'user_id' not in session or (session['user_id'] != idea.submitter_id and session.get('role') != 'admin'):
        flash(_('غير مصرح لك','Not authorized'))
        return redirect(url_for('index'))

    if idea.image:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], idea.image))
        except:
            pass

    db.session.delete(idea)
    db.session.commit()
    flash(_('تم حذف الفكرة!','Idea deleted!'))
    return redirect(url_for('index'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash(_('اسم المستخدم موجود','Username exists'))
            return redirect(url_for('register'))

        user = User(username=username, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash(_('تم التسجيل! يرجى تسجيل الدخول','Registered! Please login'))
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(_('تم تسجيل الدخول!','Logged in!'))
            return redirect(url_for('index'))
        flash(_('بيانات الدخول غير صحيحة','Invalid credentials'))
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash(_('تم تسجيل الخروج','Logged out'))
    return redirect(url_for('login'))

@app.route('/vote/<int:idea_id>', methods=['POST'])
def vote(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    idea.votes += 1
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/downvote/<int:idea_id>', methods=['POST'])
def downvote(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    idea.downvotes += 1
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/idea/<int:idea_id>', methods=['GET','POST'])
def idea_detail(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    if request.method == 'POST':
        if 'user_id' not in session:
            flash(_('يجب تسجيل الدخول للتعليق','Login to comment'))
            return redirect(url_for('login'))

        content = request.form['content'].strip()
        if content:
            comment = Comment(content=content, idea_id=idea.id, user_id=session['user_id'])
            db.session.add(comment)
            db.session.commit()
            flash(_('تم إضافة التعليق!','Comment added!'))
        else:
            flash(_('التعليق فارغ!','Comment is empty!'))
        return redirect(url_for('idea_detail', idea_id=idea.id))

    return render_template('idea_detail.html', idea=idea)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

