from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
from datetime import datetime

# Try importing genai, but continue if it fails
try:
    from google import genai
    GENAI_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not import google.genai: {e}")
    print("Summary generation will use demo mode.")
    genai = None
    GENAI_AVAILABLE = False


app = Flask(__name__, template_folder='templates')
app.secret_key = 'your-secret-key-here'

# Configure Gemini API
API_KEY = os.environ.get('GEMINI_API_KEY', None)
if GENAI_AVAILABLE and API_KEY and API_KEY != 'YOUR_API_KEY_HERE':
    try:
        client = genai.Client(api_key=API_KEY)
    except Exception as e:
        print(f"Warning: Failed to configure Gemini API: {e}")
        client = None
elif not GENAI_AVAILABLE:
    print("Warning: google.genai not available. Summary generation will use demo mode.")
    client = None
else:
    print("Warning: GEMINI_API_KEY environment variable not set or invalid. Summary generation will use demo mode.")
    client = None

# File upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'ppt', 'pptx', 'jpg', 'jpeg', 'png', 'txt', 'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# configure a simple admin email (change via env if desired)
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')

# Database setup
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT NOT NULL,
            college TEXT NOT NULL,
            branch TEXT NOT NULL,
            semester TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            semester TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            year_batch TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size INTEGER,
            privacy TEXT DEFAULT 'Public',
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Add privacy column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE resources ADD COLUMN privacy TEXT DEFAULT 'Public'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add approval_status column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE resources ADD COLUMN approval_status TEXT DEFAULT 'approved'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add blocked column to users table if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN blocked INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create reviews table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            review_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(resource_id, user_id)
        )
    ''')
    
    # Create download history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS download_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_resource_rating(resource_id):
    """Get average rating and review count for a resource"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            COALESCE(AVG(rating), 0) as avg_rating,
            COUNT(*) as review_count
        FROM reviews
        WHERE resource_id = ?
    ''', (resource_id,))
    result = cursor.fetchone()
    conn.close()
    return {
        'avg_rating': round(result['avg_rating'], 1) if result['avg_rating'] else 0,
        'review_count': result['review_count']
    }

def get_user_review(resource_id, user_id):
    """Get user's review for a specific resource"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM reviews
        WHERE resource_id = ? AND user_id = ?
    ''', (resource_id, user_id))
    review = cursor.fetchone()
    conn.close()
    return dict(review) if review else None

# Initialize database
init_db()

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')
        college = request.form.get('college')
        branch = request.form.get('branch')
        semester = request.form.get('semester')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            flash('Email already exists!', 'error')
            return redirect(url_for('signup'))
        
        # Insert new user
        hashed_password = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (name, email, password, phone, college, branch, semester)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, email, hashed_password, phone, college, branch, semester))
        
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check for admin login first
        if email == 'd@gmail.com' and password == '123':
            session['user'] = email
            session['student_id'] = 0  # Admin doesn't have a student ID
            session['user_type'] = 'admin'
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user'] = email
            # store user id for later API calls
            session['student_id'] = user['id']
            # simple role: treat ADMIN_EMAIL as admin
            session['user_type'] = 'admin' if email == ADMIN_EMAIL else 'student'
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return redirect(url_for('login'))
    
    # Get user's uploaded resources
    cursor.execute('''
        SELECT * FROM resources 
        WHERE user_id = ? 
        ORDER BY upload_date DESC
    ''', (user['id'],))
    resources = [dict(row) for row in cursor.fetchall()]
    
    # Get download count
    cursor.execute('SELECT COUNT(*) as count FROM download_history WHERE user_id = ?', (user['id'],))
    download_count = cursor.fetchone()['count']
    
    conn.close()
    
    user_data = {
        'name': user['name'],
        'phone': user['phone'],
        'college': user['college'],
        'branch': user['branch'],
        'semester': user['semester'],
        'download_count': download_count
    }
    
    return render_template('dashboard.html', user=user_data, resources=resources)

@app.route('/upload_page')
def upload_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return redirect(url_for('login'))
    
    # Get user's uploaded resources
    cursor.execute('''
        SELECT * FROM resources 
        WHERE user_id = ? 
        ORDER BY upload_date DESC
    ''', (user['id'],))
    resources = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('upload_page.html', resources=resources)

@app.route('/upload_resource', methods=['POST'])
def upload_resource():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Get form data
    title = request.form.get('title')
    subject = request.form.get('subject')
    semester = request.form.get('semester')
    resource_type = request.form.get('resource_type')
    year_batch = request.form.get('year_batch')
    description = request.form.get('description', '')
    tags = request.form.get('tags', '')
    privacy = request.form.get('privacy', 'Public')
    
    # Check if file is present
    if 'file' not in request.files:
        flash('No file selected!', 'error')
        return redirect(url_for('dashboard'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected!', 'error')
        return redirect(url_for('dashboard'))
    
    if file and allowed_file(file.filename):
        # Secure the filename and add timestamp
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{original_filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save file
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        
        # Get user ID
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (session['user'],))
        user = cursor.fetchone()
        
        # Insert resource into database
        cursor.execute('''
            INSERT INTO resources 
            (user_id, title, subject, semester, resource_type, year_batch, description, tags, filename, original_filename, file_size, privacy, approval_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user['id'], title, subject, semester, resource_type, year_batch, description, tags, filename, original_filename, file_size, privacy, 'pending'))
        
        conn.commit()
        conn.close()
        
        flash('Resource uploaded successfully!', 'success')
    else:
        flash('Invalid file type! Allowed types: PDF, DOCX, PPT, Images, TXT, ZIP', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/edit_resource/<int:resource_id>', methods=['POST'])
def edit_resource(resource_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user ID
    cursor.execute('SELECT id FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    
    # Check if resource belongs to user
    cursor.execute('SELECT * FROM resources WHERE id = ? AND user_id = ?', (resource_id, user['id']))
    resource = cursor.fetchone()
    
    if not resource:
        flash('Resource not found or unauthorized!', 'error')
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Update resource
    title = request.form.get('title')
    subject = request.form.get('subject')
    semester = request.form.get('semester')
    resource_type = request.form.get('resource_type')
    year_batch = request.form.get('year_batch')
    description = request.form.get('description', '')
    tags = request.form.get('tags', '')
    privacy = request.form.get('privacy', 'Public')
    
    cursor.execute('''
        UPDATE resources 
        SET title = ?, subject = ?, semester = ?, resource_type = ?, year_batch = ?, description = ?, tags = ?, privacy = ?
        WHERE id = ?
    ''', (title, subject, semester, resource_type, year_batch, description, tags, privacy, resource_id))
    
    conn.commit()
    conn.close()
    
    flash('Resource updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete_resource/<int:resource_id>')
def delete_resource(resource_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user ID
    cursor.execute('SELECT id FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    
    # Check if resource belongs to user
    cursor.execute('SELECT * FROM resources WHERE id = ? AND user_id = ?', (resource_id, user['id']))
    resource = cursor.fetchone()
    
    if not resource:
        flash('Resource not found or unauthorized!', 'error')
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Delete file from filesystem
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], resource['filename'])
    if os.path.exists(filepath):
        os.remove(filepath)
    
    # Delete from database
    cursor.execute('DELETE FROM resources WHERE id = ?', (resource_id,))
    conn.commit()
    conn.close()
    
    flash('Resource deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/download/<int:resource_id>')
def download_resource(resource_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current user info
    cursor.execute('SELECT * FROM users WHERE email = ?', (session['user'],))
    current_user = cursor.fetchone()
    
    # Get resource with uploader info
    cursor.execute('''
        SELECT r.*, u.college as uploader_college 
        FROM resources r
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
    ''', (resource_id,))
    resource = cursor.fetchone()
    
    if not resource:
        conn.close()
        flash('Resource not found!', 'error')
        return redirect(url_for('dashboard'))
    
    # Check privacy access
    if resource['privacy'] == 'Private':
        if current_user['college'] != resource['uploader_college']:
            conn.close()
            flash('Access denied! This resource is private and only available to students from ' + resource['uploader_college'], 'error')
            return redirect(url_for('access_resources'))
    
    # Record download in history
    try:
        cursor.execute('''
            INSERT INTO download_history (resource_id, user_id)
            VALUES (?, ?)
        ''', (resource_id, current_user['id']))
        conn.commit()
    except Exception as e:
        print(f"Error recording download: {e}")
    
    conn.close()
    
    return send_from_directory(app.config['UPLOAD_FOLDER'], resource['filename'], as_attachment=True, download_name=resource['original_filename'])


@app.route('/my_resources')
def my_resources():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return redirect(url_for('login'))
    
    # Get user's uploaded resources with ratings
    cursor.execute('''
        SELECT * FROM resources 
        WHERE user_id = ? 
        ORDER BY upload_date DESC
    ''', (user['id'],))
    resources = []
    for row in cursor.fetchall():
        resource_dict = dict(row)
        rating_info = get_resource_rating(row['id'])
        resource_dict['avg_rating'] = rating_info['avg_rating']
        resource_dict['review_count'] = rating_info['review_count']
        resources.append(resource_dict)
    
    conn.close()
    
    return render_template('my_resources.html', resources=resources, user=user)


@app.route('/download_history')
def download_history():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return redirect(url_for('login'))
    
    # Get download history with resource details
    cursor.execute('''
        SELECT 
            dh.id,
            dh.download_date,
            r.id as resource_id,
            r.title,
            r.subject,
            r.resource_type,
            r.semester,
            r.year_batch,
            r.privacy,
            u.name as uploader_name,
            u.college as uploader_college
        FROM download_history dh
        JOIN resources r ON dh.resource_id = r.id
        JOIN users u ON r.user_id = u.id
        WHERE dh.user_id = ?
        ORDER BY dh.download_date DESC
    ''', (user['id'],))
    
    downloads = [dict(row) for row in cursor.fetchall()]
    
    # Add rating info for each resource
    for download in downloads:
        rating_info = get_resource_rating(download['resource_id'])
        download['avg_rating'] = rating_info['avg_rating']
        download['review_count'] = rating_info['review_count']
    
    # Get statistics
    cursor.execute('SELECT COUNT(*) as count FROM download_history WHERE user_id = ?', (user['id'],))
    total_downloads = cursor.fetchone()['count']
    
    cursor.execute('''
        SELECT COUNT(DISTINCT resource_id) as count 
        FROM download_history 
        WHERE user_id = ?
    ''', (user['id'],))
    unique_resources = cursor.fetchone()['count']
    
    conn.close()
    
    stats = {
        'total_downloads': total_downloads,
        'unique_resources': unique_resources
    }
    
    return render_template('download_history.html', user=user, downloads=downloads, stats=stats)


@app.route('/my_profile')
def my_profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return redirect(url_for('login'))
    
    # Get user statistics
    cursor.execute('SELECT COUNT(*) as count FROM resources WHERE user_id = ?', (user['id'],))
    upload_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM reviews WHERE user_id = ?', (user['id'],))
    review_count = cursor.fetchone()['count']
    
    cursor.execute('SELECT COUNT(*) as count FROM download_history WHERE user_id = ?', (user['id'],))
    download_count = cursor.fetchone()['count']
    
    conn.close()
    
    user_data = {
        'name': user['name'],
        'email': user['email'],
        'phone': user['phone'],
        'college': user['college'],
        'branch': user['branch'],
        'semester': user['semester'],
        'upload_count': upload_count,
        'review_count': review_count,
        'download_count': download_count
    }
    
    return render_template('my_profile.html', user=user_data)


@app.route('/access_resources')
def access_resources():
    if 'user' not in session:
        flash('Please login to access resources', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current user using student_id if available, otherwise email
    if 'student_id' in session and session['student_id']:
        cursor.execute("SELECT * FROM users WHERE id=?", (session['student_id'],))
    else:
        cursor.execute('SELECT * FROM users WHERE email = ?', (session['user'],))
    
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        session.clear()
        flash('User not found. Please login again.', 'error')
        return redirect(url_for('login'))
    
    # Get ALL approved resources (public + private)
    cursor.execute("""
        SELECT r.*, u.name as uploader_name,
               u.college as uploader_college,
               u.branch as uploader_branch
        FROM resources r
        JOIN users u ON r.user_id = u.id
        WHERE r.approval_status = 'approved'
        ORDER BY r.upload_date DESC
    """)
    resources = cursor.fetchall()
    
    resource_list = []
    for resource in resources:
        # Determine accessibility
        accessible = (resource['privacy'] == 'Public' or
                     (resource['privacy'] == 'Private' and
                      resource['uploader_college'] == user['college']))
        
        # Get rating
        rating_info = get_resource_rating(resource['id'])
        
        resource_list.append({
            **dict(resource),
            "accessible": accessible,
            "avg_rating": rating_info['avg_rating'],
            "review_count": rating_info['review_count']
        })
    
    conn.close()
    
    return render_template("access_resources.html",
                         resources=resource_list,
                         user=user)


@app.route('/resource/<int:resource_id>')
def resource_detail(resource_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current user info
    cursor.execute('SELECT * FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    
    # Get resource with uploader info
    cursor.execute('''
        SELECT r.*, u.name as uploader_name, u.college as uploader_college, u.branch as uploader_branch
        FROM resources r
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
    ''', (resource_id,))
    resource = cursor.fetchone()
    
    if not resource:
        conn.close()
        flash('Resource not found!', 'error')
        return redirect(url_for('access_resources'))
    
    resource_dict = dict(resource)
    
    # Check accessibility
    if resource['privacy'] == 'Public':
        resource_dict['accessible'] = True
    elif resource['privacy'] == 'Private' and resource['uploader_college'] == user['college']:
        resource_dict['accessible'] = True
    else:
        resource_dict['accessible'] = False
    
    # Get rating information
    rating_info = get_resource_rating(resource_id)
    resource_dict['avg_rating'] = rating_info['avg_rating']
    resource_dict['review_count'] = rating_info['review_count']
    
    # Get all reviews with user info
    cursor.execute('''
        SELECT r.*, u.name as reviewer_name
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.resource_id = ?
        ORDER BY r.created_at DESC
    ''', (resource_id,))
    reviews = [dict(row) for row in cursor.fetchall()]
    
    # Get current user's review if exists
    user_review = get_user_review(resource_id, user['id'])
    
    conn.close()
    
    return render_template('resource_detail.html', 
                         resource=resource_dict, 
                         reviews=reviews, 
                         user_review=user_review,
                         user=user)


@app.route('/submit_review/<int:resource_id>', methods=['POST'])
def submit_review(resource_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    rating = request.form.get('rating', type=int)
    review_text = request.form.get('review_text', '').strip()
    
    if not rating or rating < 1 or rating > 5:
        flash('Please provide a valid rating (1-5 stars)', 'error')
        return redirect(url_for('resource_detail', resource_id=resource_id))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user ID
    cursor.execute('SELECT id FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    
    # Check if user already reviewed this resource
    existing_review = get_user_review(resource_id, user['id'])
    
    try:
        if existing_review:
            # Update existing review
            cursor.execute('''
                UPDATE reviews 
                SET rating = ?, review_text = ?, updated_at = CURRENT_TIMESTAMP
                WHERE resource_id = ? AND user_id = ?
            ''', (rating, review_text, resource_id, user['id']))
            flash('Your review has been updated!', 'success')
        else:
            # Insert new review
            cursor.execute('''
                INSERT INTO reviews (resource_id, user_id, rating, review_text)
                VALUES (?, ?, ?, ?)
            ''', (resource_id, user['id'], rating, review_text))
            flash('Your review has been submitted!', 'success')
        
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Error submitting review. Please try again.', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('resource_detail', resource_id=resource_id))


@app.route('/delete_review/<int:resource_id>')
def delete_review(resource_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user ID
    cursor.execute('SELECT id FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    
    # Delete review
    cursor.execute('''
        DELETE FROM reviews 
        WHERE resource_id = ? AND user_id = ?
    ''', (resource_id, user['id']))
    
    conn.commit()
    conn.close()
    
    flash('Your review has been deleted!', 'success')
    return redirect(url_for('resource_detail', resource_id=resource_id))


@app.route('/get_student_info', methods=['GET'])
def get_student_info():
    if session.get('user_type') != 'student' and session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    # prefer student_id if present
    sid = session.get('student_id')
    if sid:
        cursor.execute('SELECT * FROM users WHERE id = ?', (sid,))
    else:
        cursor.execute('SELECT * FROM users WHERE email = ?', (session.get('user'),))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    # we don't have a USN column in the current schema; synthesize one using id
    usn = f"U{user['id']:04d}"

    return jsonify({
        'success': True,
        'student': {
            'name': user['name'],
            'usn': usn,
            'email': user['email'],
            'department': user['branch'],
            'semester': user['semester']
        }
    })

@app.route('/resource_snapshot', methods=['GET', 'POST'])
def resource_snapshot():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        content = request.form.get('content')

        # Word count validation
        word_count = len(content.split())

        if word_count > 10000:
            flash('Content exceeds 10,000 word limit!', 'error')
            return redirect(url_for('resource_snapshot'))

        flash(f'Resource snapshot saved successfully! Word count: {word_count}', 'success')
        return redirect(url_for('resource_snapshot'))

    return render_template('resource_snapshot.html')


@app.route('/generate_summary', methods=['POST'])
def generate_summary():
    if 'user' not in session:
        return redirect(url_for('login'))

    content = request.form.get('content', '').strip()

    if not content:
        flash("Please enter content", "error")
        return redirect(url_for('resource_snapshot'))

    try:
        if not client:
            raise Exception("Gemini API client not configured")
        
        prompt = f"""
        Summarize these study notes in a clear and organized manner, capturing the main topics, key concepts, and important details. Provide a comprehensive summary that helps students understand the core content:

        Content:
        {content}
        """

        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        
        # Access the response text
        summary = response.text.strip()

        return render_template("summary_result.html", summary=summary)

    except Exception as e:
        import traceback
        print("Error generating summary:")
        traceback.print_exc()
        
        # Fallback: Generate a simple summary without API
        words = content.split()
        if len(words) > 50:
            simple_summary = ' '.join(words[:50]) + '...\n\n[Note: AI summary unavailable. Please set valid GEMINI_API_KEY environment variable. Showing first 50 words as preview.]'
        else:
            simple_summary = content + '\n\n[Note: AI summary unavailable. Please set valid GEMINI_API_KEY environment variable.]'
        
        return render_template("summary_result.html", summary=simple_summary)



@app.route('/knowledge_hub')
def knowledge_hub():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (session['user'],))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return redirect(url_for('login'))
    
    return render_template('knowledge_hub.html', user=user)


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all pending resources for approval
    cursor.execute('''
        SELECT r.*, u.name as uploader_name, u.email as uploader_email, u.college as uploader_college
        FROM resources r
        JOIN users u ON r.user_id = u.id
        WHERE r.approval_status = 'pending'
        ORDER BY r.upload_date DESC
    ''')
    pending_resources = [dict(row) for row in cursor.fetchall()]
    
    # Get approved resources count
    cursor.execute("SELECT COUNT(*) as count FROM resources WHERE approval_status = 'approved'")
    approved_count = cursor.fetchone()['count']
    
    # Get rejected resources count
    cursor.execute("SELECT COUNT(*) as count FROM resources WHERE approval_status = 'rejected'")
    rejected_count = cursor.fetchone()['count']
    
    # Get total resources count
    cursor.execute("SELECT COUNT(*) as count FROM resources")
    total_count = cursor.fetchone()['count']
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         pending_resources=pending_resources,
                         approved_count=approved_count,
                         rejected_count=rejected_count,
                         total_count=total_count)


@app.route('/approve_resource/<int:resource_id>', methods=['POST'])
def approve_resource(resource_id):
    if 'user' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE resources SET approval_status = 'approved' WHERE id = ?", (resource_id,))
    conn.commit()
    conn.close()
    
    flash('Resource approved successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/reject_resource/<int:resource_id>', methods=['POST'])
def reject_resource(resource_id):
    if 'user' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE resources SET approval_status = 'rejected' WHERE id = ?", (resource_id,))
    conn.commit()
    conn.close()
    
    flash('Resource rejected!', 'error')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin_users')
def admin_users():
    if 'user' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all users (excluding admin)
    cursor.execute('''
        SELECT id, name, email, phone, college, branch, semester, 
               COALESCE(blocked, 0) as blocked
        FROM users 
        WHERE email != ?
        ORDER BY name
    ''', (ADMIN_EMAIL,))
    users = [dict(row) for row in cursor.fetchall()]
    
    # Get user statistics
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE email != ?", (ADMIN_EMAIL,))
    total_users = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE COALESCE(blocked, 0) = 1 AND email != ?", (ADMIN_EMAIL,))
    blocked_users = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE COALESCE(blocked, 0) = 0 AND email != ?", (ADMIN_EMAIL,))
    active_users = cursor.fetchone()['count']
    
    conn.close()
    
    return render_template('admin_users.html', 
                         users=users,
                         total_users=total_users,
                         blocked_users=blocked_users,
                         active_users=active_users)


@app.route('/block_user/<int:user_id>', methods=['POST'])
def block_user(user_id):
    if 'user' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current blocked status
    cursor.execute("SELECT blocked FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user:
        new_status = 0 if user['blocked'] == 1 else 1
        cursor.execute("UPDATE users SET blocked = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
        
        if new_status == 1:
            flash('User has been blocked!', 'error')
        else:
            flash('User has been unblocked!', 'success')
    
    conn.close()
    return redirect(url_for('admin_users'))


@app.route('/admin_resources')
def admin_resources():
    if 'user' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all resources
    cursor.execute('''
        SELECT r.*, u.name as uploader_name, u.email as uploader_email, u.college as uploader_college
        FROM resources r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.upload_date DESC
    ''')
    resources = [dict(row) for row in cursor.fetchall()]
    
    # Get statistics
    cursor.execute("SELECT COUNT(*) as count FROM resources")
    total_resources = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM resources WHERE approval_status = 'approved'")
    approved = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM resources WHERE approval_status = 'pending'")
    pending = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM resources WHERE approval_status = 'rejected'")
    rejected = cursor.fetchone()['count']
    
    conn.close()
    
    return render_template('admin_resources.html',
                         resources=resources,
                         total_resources=total_resources,
                         approved=approved,
                         pending=pending,
                         rejected=rejected)


@app.route('/admin_delete_resource/<int:resource_id>', methods=['POST'])
def admin_delete_resource(resource_id):
    if 'user' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get resource info
    cursor.execute('SELECT * FROM resources WHERE id = ?', (resource_id,))
    resource = cursor.fetchone()
    
    if resource:
        # Delete file from filesystem
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], resource['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Delete from database
        cursor.execute('DELETE FROM resources WHERE id = ?', (resource_id,))
        conn.commit()
        flash('Resource deleted successfully!', 'success')
    else:
        flash('Resource not found!', 'error')
    
    conn.close()
    return redirect(url_for('admin_resources'))


@app.route('/admin_delete_resources', methods=['POST'])
def admin_delete_resources():
    if 'user' not in session or session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'success': False, 'message': 'No resources selected'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    deleted_count = 0
    for resource_id in ids:
        cursor.execute('SELECT * FROM resources WHERE id = ?', (resource_id,))
        resource = cursor.fetchone()
        
        if resource:
            # Delete file from filesystem
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], resource['filename'])
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Error deleting file: {e}")
            
            # Delete from database
            cursor.execute('DELETE FROM resources WHERE id = ?', (resource_id,))
            deleted_count += 1
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': f'Successfully deleted {deleted_count} resource(s)'
    })


@app.route('/admin_delete_all_resources', methods=['POST'])
def admin_delete_all_resources():
    if 'user' not in session or session.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all resources
    cursor.execute('SELECT * FROM resources')
    resources = cursor.fetchall()
    
    deleted_count = 0
    for resource in resources:
        # Delete file from filesystem
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], resource['filename'])
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Error deleting file: {e}")
        deleted_count += 1
    
    # Delete all resources from database
    cursor.execute('DELETE FROM resources')
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': f'Successfully deleted all {deleted_count} resource(s)'
    })


@app.route('/view_resource/<int:resource_id>')
def view_resource(resource_id):
    if 'user' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT r.*, u.name as uploader_name, u.email as uploader_email, u.college as uploader_college
        FROM resources r
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
    ''', (resource_id,))
    resource = dict(cursor.fetchone())
    
    conn.close()
    
    # Get the file extension
    file_ext = resource['filename'].split('.')[-1].lower() if resource['filename'] else ''
    
    # For images, return directly; for other files, show details
    if file_ext in ['jpg', 'jpeg', 'png', 'gif']:
        return render_template('view_resource_image.html', resource=resource)
    else:
        return render_template('view_resource_file.html', resource=resource)


@app.route('/admin_upload_resource', methods=['GET', 'POST'])
def admin_upload_resource():
    if 'user' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        subject = request.form.get('subject')
        semester = request.form.get('semester')
        resource_type = request.form.get('resource_type')
        year_batch = request.form.get('year_batch')
        description = request.form.get('description')
        privacy = request.form.get('privacy', 'Public')
        
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            
            # Get admin user id
            admin_email = session.get('user')
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ?", (admin_email,))
            admin_user = cursor.fetchone()
            
            if admin_user:
                cursor.execute('''
                    INSERT INTO resources (user_id, title, subject, semester, resource_type, 
                                         year_batch, description, filename, original_filename, 
                                         file_size, privacy, approval_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved')
                ''', (admin_user['id'], title, subject, semester, resource_type, 
                     year_batch, description, unique_filename, filename,
                     os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)),
                     privacy))
                conn.commit()
                flash('Resource uploaded successfully!', 'success')
            
            conn.close()
            return redirect(url_for('admin_resources'))
    
    return render_template('admin_upload_resource.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Initialize database to add blocked column if needed
    init_db()
    app.run(debug=True)
