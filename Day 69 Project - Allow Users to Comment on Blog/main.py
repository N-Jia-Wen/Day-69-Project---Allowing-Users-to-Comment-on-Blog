from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, request, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    # As the child of User:
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("user.id"))
    # posts refer to property in User class.
    author = relationship("User", back_populates="posts")

    # As the parent of Comment:
    comments = relationship("Comment", back_populates="parent_post")


class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(1000), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # As the child of User:
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("user.id"))
    comment_author = relationship("User", back_populates="comments")

    # As the child of BlogPost:
    post_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")


with app.app_context():
    db.create_all()


# Custom decorator to ensure users other than admin (of id = 1) cannot edit, create, or delete posts.
def admin_only(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if current_user.get_id() == "1":
            return function(*args, **kwargs)
        else:
            return abort(403)

    return decorated_function


@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "GET":
        register_form = RegisterForm()
        return render_template("register.html", form=register_form)
    elif request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = generate_password_hash(
            request.form.get("password"),
            method="pbkdf2:sha256",
            salt_length=8
        )
        existing_user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if existing_user is None:

            new_user = User(name=name, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)
            # flash("Get flash message up and running so user knows they have registered successfully.")
            return redirect(url_for('get_all_posts'))
        else:
            flash("Your account associated with that email already exists. Please log in instead.")
            return redirect(url_for('login'))


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user_profile = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user_profile is not None:

            if check_password_hash(user_profile.password, password) is True:
                login_user(user_profile)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Incorrect password. Please try again.")

        else:
            flash("Email has not been registered.")

    # Code reaches here if a. User makes get request, b. User has not registered yet, c. User types incorrect pw.
    login_form = LoginForm()
    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form = CommentForm()

    if request.method == "POST":
        if current_user.is_authenticated is False:
            flash("Please log in to make comments.")
            return redirect(url_for('login'))
        else:
            new_comment = Comment(text=request.form.get("comment"),
                                  comment_author=current_user,
                                  parent_post=requested_post)
            db.session.add(new_comment)
            db.session.commit()

    return render_template("post.html", post=requested_post,
                           comment_form=comment_form, gravatar=gravatar)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True, port=5002)
