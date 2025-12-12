# 🏦 Savings Web Application (Capstone)

![Status](https://img.shields.io/badge/Status-In%20Development-yellow?style=for-the-badge)
![Tech Stack](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Security](https://img.shields.io/badge/Security-RBAC-blue?style=for-the-badge)

> **A secure, scalable financial management platform for community savings groups, built to bridge the gap between theoretical backend concepts and production-ready engineering.**

---

## 📖 About The Project

The **Welfare Contribution System** is a robust backend solution designed to digitize the operations of community welfare groups. It replaces manual ledgers with a secure, automated digital book.

This project was born out of a desire to move beyond passive learning. I paused my standard curriculum to embrace **Project-Based Learning**, challenging myself to build a system that handles real-world constraints like financial accuracy, data privacy, and complex user relationships.

### 🎯 The Problem
Community groups often struggle with:
* Lack of transparency in financial records.
* Manual errors in calculating balances and arrears.
* Security risks associated with physical ledgers.

### 💡 The Solution
A Django-powered application featuring:
* **Strict Separation of Concerns:** distinct apps for User Identity vs. Financial Transactions.
* **Role-Based Access Control (RBAC):** Admins see the global ledger; Members see only their personal history.
* **Automated Logic:** System-calculated totals preventing human math errors.

---

## ⚙️ Technical Architecture

This project follows a modular design pattern to ensure scalability and maintainability.

| Application | Responsibility | Key Components |
| :--- | :--- | :--- |
| **`accounts` (groups)** | **Identity & Access** | Custom Member Models, OneToOne User Linking, Auth Views. |
| **`contributions`** | **Financial Engine** | Transaction Ledger, Aggregation Logic, Secure Admin Dashboard. |

### Key Technical Highlights
* **Security First:** Implementation of Python decorators (`@user_passes_test`) to enforce strict admin-only access on sensitive views.
* **Data Integrity:** Usage of `OneToOneFields` to extend the standard Django User model without polluting the core authentication system.
* **Dynamic Routing:** App-specific `urls.py` modules wired into a central configuration for clean, readable routing logic.

---

## 🗺️ Execution Roadmap

I am following a structured, agile-inspired development plan divided into clear technical phases.

### 🏗️ Phase 1: Foundation & Data Architecture (Completed)
- [x] Project Initialization & Environment Setup.
- [x] `Group` & `Cycle` Model Architecture.
- [x] `Member` Model Design (OneToOne User Linking).
- [x] `Contribution` Model (Financial Ledger).
- [x] Admin Interface Configuration & Migrations.

### 🔑 Phase 2: Auth & Core Logic (Current Focus)
- [x] Authentication System (Login/Logout Views).
- [x] **Secure Admin Dashboard Implementation.** *(Current Milestone)*
- [ ] Member CRUD Views (Admin Forms).
- [ ] **Automated User Creation Logic (Overriding `save()` methods).**
- [ ] Member Portal & Permissions.

### 💵 Phase 3: The Transaction Engine
- [ ] Optimized Contribution Forms.
- [ ] POST Request Handling & Validation.
- [ ] The Digital Ledger View (DataTables).
- [ ] Aggregation Logic (Calculating "Kitty" Totals).
- [ ] Admin Dashboard Reporting Integration.

### 🛡️ Phase 4: Security & Member Experience
- [ ] Individual Member Balance Logic.
- [ ] Member Portal Data Injection.
- [ ] Filtered Transaction History.
- [ ] Strict Permission Auditing.
- [ ] UI/UX Polish (Bootstrap Integration).

### 🚢 Phase 5: Testing & Deployment
- [ ] Admin Workflow Stress Testing.
- [ ] Member Security Verification.
- [ ] Code Refactoring & Optimization.
- [ ] Documentation Finalization.
- [ ] **Live Deployment (Render/Railway).**

---

## 🚀 Getting Started Locally

Want to see the code in action? Follow these steps:

1.  **Clone the repo**
    ```bash
    git clone [https://github.com/joedrake0909/Alx_Capstone_Project.git)
    cd welfare-contribution-system  or core
    ```

2.  **Create Virtual Environment**
    ```bash
    # Windows
    python -m venv venv
    venv\Scripts\activate

    # Mac/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run Migrations**
    ```bash
    python manage.py migrate
    ```

5.  **Create Superuser**
    ```bash
    python manage.py createsuperuser
    ```

6.  **Run Server**
    ```bash
    python manage.py runserver
    ```

---

## 👨‍💻 Author

**Joseph Apelete Biossey**
*Backend Engineering Student @ ALX*

I am documenting my journey from "Tutorial Hell" to **Software Engineer**. Connect with me to see how this project evolves!

[![LinkedIn](https://www.linkedin.com/in/joseph-biossey-31376a292/)
[![GitHub](https://github.com/joedrake0909)

---
*Built with ❤️ as part of the ALX Software Engineering Capstone.*