# 📚 Student Resource Sharing & Knowledge Hub

## 📖 Project Overview

The **Student Resource Sharing & Knowledge Hub** is a web-based application developed using **Python Flask** that allows students to upload, share, download, and review academic resources such as notes, PDFs, presentations, and documents.

The platform also includes features like **resource approval by admin, rating and reviews, download history tracking, and AI-powered summary generation** to help students quickly understand study materials.

This system improves collaboration among students and creates a centralized academic resource repository.

---

## 🚀 Features

### 👨‍🎓 Student Features

- User Registration and Login
- Upload study resources (PDF, DOC, PPT, Images, etc.)
- Download academic resources
- View and manage uploaded resources
- Rating and review system for resources
- Download history tracking
- Profile management
- Resource privacy (Public / College-only access)
- AI-generated summary of study notes

### 🛠 Admin Features

- Admin dashboard
- Approve or reject uploaded resources
- Manage all users
- Block or unblock users
- Delete inappropriate resources
- Upload resources directly as admin

---

## 🧑‍💻 Technologies Used

### Frontend

- HTML
- CSS
- JavaScript
- Jinja2 Templates

### Backend

- Python
- Flask Framework

### Database

- SQLite

### Additional Libraries

- Werkzeug (Password security)
- Google Gemini API (AI summary generation)

---

## 📂 Project Structure



project/
│
├── templates/
│   ├── login.html
│   ├── signup.html
│   ├── dashboard.html
│   └── access_resources.html
│
├── uploads/
│
├── app.py
├── users.db
└── README.md





---

## 🔒 Security Features

- Password hashing using **Werkzeug**
- Secure file uploads
- File type validation
- Session-based authentication
- Resource access control

---

## 📊 Database Tables

The SQLite database contains the following tables:

- **users** – Stores user account information
- **resources** – Stores uploaded study resources
- **reviews** – Stores ratings and reviews
- **download_history** – Tracks downloaded resources

---

## 🔮 Future Enhancements

- Email verification system
- Advanced search and filters
- Mobile responsive UI
- Resource recommendation system
- Cloud storage integration
- Online collaboration features

---

## 👨‍💻 Author

**Darshan Hegde**

---

## 📜 License

This project is developed for **educational purposes only**.
