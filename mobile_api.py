from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
import json

# Create blueprint
mobile_api = Blueprint('mobile_api', __name__, url_prefix='/api/mobile')

@mobile_api.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok', 
        'message': 'Mobile API is running',
        'timestamp': datetime.utcnow().isoformat()
    })

@mobile_api.route('/login', methods=['POST'])
def mobile_login():
    """Mobile login endpoint"""
    try:
        data = request.get_json()
        
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({
                'success': False,
                'message': 'Username and password are required'
            }), 400
        
        # Import here to avoid circular imports
        from app import User
        
        user = User.query.filter_by(username=data['username']).first()
        
        if user and user.check_password(data['password']) and user.is_active:
            # Create access token
            access_token = create_access_token(
                identity=user.id,
                expires_delta=timedelta(days=7)
            )
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'access_token': access_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'full_name': user.full_name,
                    'email': user.email,
                    'role': user.role
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid credentials'
            }), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Login failed: {str(e)}'
        }), 500

@mobile_api.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get user profile"""
    try:
        user_id = get_jwt_identity()
        
        # Import here to avoid circular imports
        from app import User
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'email': user.email,
                'phone': user.phone,
                'role': user.role,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get profile: {str(e)}'
        }), 500

@mobile_api.route('/students', methods=['GET'])
@jwt_required()
def get_students():
    """Get students for parent"""
    try:
        user_id = get_jwt_identity()
        
        # Import here to avoid circular imports
        from app import User, Student
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        if user.role != 'parent':
            return jsonify({
                'success': False,
                'message': 'Access denied. Parent role required.'
            }), 403
        
        students = Student.query.filter_by(parent_id=user_id, is_active=True).all()
        
        students_data = []
        for student in students:
            students_data.append({
                'id': student.id,
                'admission_number': student.admission_number,
                'full_name': student.full_name,
                'current_class': student.current_class,
                'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else None,
                'age': student.age,
                'created_at': student.created_at.isoformat() if student.created_at else None
            })
        
        return jsonify({
            'success': True,
            'students': students_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get students: {str(e)}'
        }), 500

@mobile_api.route('/student/<int:student_id>/grades', methods=['GET'])
@jwt_required()
def get_student_grades(student_id):
    """Get grades for a specific student"""
    try:
        user_id = get_jwt_identity()
        
        # Import here to avoid circular imports
        from app import User, Student, Grade, Subject
        
        user = User.query.get(user_id)
        student = Student.query.get(student_id)
        
        if not user or not student:
            return jsonify({
                'success': False,
                'message': 'User or student not found'
            }), 404
        
        # Check access permissions
        if user.role == 'parent' and student.parent_id != user_id:
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Get query parameters
        year = request.args.get('year', datetime.now().year, type=int)
        term = request.args.get('term')
        
        # Build query
        query = Grade.query.filter_by(student_id=student_id, year=year)
        if term:
            query = query.filter_by(term=term)
        
        grades = query.join(Subject).all()
        
        grades_data = []
        for grade in grades:
            grades_data.append({
                'id': grade.id,
                'subject': {
                    'id': grade.subject.id,
                    'name': grade.subject.name,
                    'code': grade.subject.code
                },
                'term': grade.term,
                'year': grade.year,
                'marks': grade.marks,
                'max_marks': grade.max_marks,
                'percentage': grade.percentage,
                'grade_letter': grade.grade_letter,
                'points': grade.points,
                'teacher_comment': grade.teacher_comment,
                'created_at': grade.created_at.isoformat() if grade.created_at else None
            })
        
        return jsonify({
            'success': True,
            'student': {
                'id': student.id,
                'full_name': student.full_name,
                'admission_number': student.admission_number,
                'current_class': student.current_class
            },
            'grades': grades_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get grades: {str(e)}'
        }), 500

@mobile_api.route('/student/<int:student_id>/fees', methods=['GET'])
@jwt_required()
def get_student_fees(student_id):
    """Get fee statements for a specific student"""
    try:
        user_id = get_jwt_identity()
        
        # Import here to avoid circular imports
        from app import User, Student, FeeStatement, FeePayment
        
        user = User.query.get(user_id)
        student = Student.query.get(student_id)
        
        if not user or not student:
            return jsonify({
                'success': False,
                'message': 'User or student not found'
            }), 404
        
        # Check access permissions
        if user.role == 'parent' and student.parent_id != user_id:
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403
        
        # Get query parameters
        year = request.args.get('year', datetime.now().year, type=int)
        
        # Get fee statements
        fee_statements = FeeStatement.query.filter_by(
            student_id=student_id,
            year=year
        ).all()
        
        fees_data = []
        total_due = 0
        total_paid = 0
        
        for fee in fee_statements:
            total_due += fee.amount_due
            total_paid += fee.amount_paid
            
            fees_data.append({
                'id': fee.id,
                'fee_type': fee.fee_type,
                'term': fee.term,
                'year': fee.year,
                'amount_due': fee.amount_due,
                'amount_paid': fee.amount_paid,
                'balance': fee.balance,
                'due_date': fee.due_date.isoformat() if fee.due_date else None,
                'is_paid': fee.is_paid,
                'is_overdue': fee.is_overdue,
                'description': fee.description,
                'created_at': fee.created_at.isoformat() if fee.created_at else None
            })
        
        # Get recent payments
        recent_payments = FeePayment.query.filter_by(
            student_id=student_id
        ).order_by(FeePayment.created_at.desc()).limit(10).all()
        
        payments_data = []
        for payment in recent_payments:
            payments_data.append({
                'id': payment.id,
                'fee_type': payment.fee_type,
                'amount_paid': payment.amount_paid,
                'payment_method': payment.payment_method,
                'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                'receipt_number': payment.receipt_number,
                'reference_number': payment.reference_number,
                'created_at': payment.created_at.isoformat() if payment.created_at else None
            })
        
        return jsonify({
            'success': True,
            'student': {
                'id': student.id,
                'full_name': student.full_name,
                'admission_number': student.admission_number,
                'current_class': student.current_class
            },
            'summary': {
                'total_due': total_due,
                'total_paid': total_paid,
                'total_balance': total_due - total_paid
            },
            'fee_statements': fees_data,
            'recent_payments': payments_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get fees: {str(e)}'
        }), 500

@mobile_api.route('/announcements', methods=['GET'])
@jwt_required()
def get_announcements():
    """Get announcements for user"""
    try:
        user_id = get_jwt_identity()
        
        # Import here to avoid circular imports
        from app import User, Announcement
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        # Get announcements based on user role
        target_audiences = ['all']
        if user.role == 'parent':
            target_audiences.append('parents')
        elif user.role == 'admin':
            target_audiences.extend(['staff', 'admin'])
        
        announcements = Announcement.query.filter(
            Announcement.is_active == True,
            Announcement.target_audience.in_(target_audiences)
        ).order_by(Announcement.created_at.desc()).limit(20).all()
        
        announcements_data = []
        for announcement in announcements:
            announcements_data.append({
                'id': announcement.id,
                'title': announcement.title,
                'content': announcement.content,
                'priority': announcement.priority,
                'target_audience': announcement.target_audience,
                'created_at': announcement.created_at.isoformat() if announcement.created_at else None,
                'expires_at': announcement.expires_at.isoformat() if announcement.expires_at else None
            })
        
        return jsonify({
            'success': True,
            'announcements': announcements_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get announcements: {str(e)}'
        }), 500

@mobile_api.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_data():
    """Get dashboard data for mobile app"""
    try:
        user_id = get_jwt_identity()
        
        # Import here to avoid circular imports
        from app import User, Student, Grade, FeeStatement, Announcement
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        dashboard_data = {
            'user': {
                'full_name': user.full_name,
                'role': user.role
            }
        }
        
        if user.role == 'parent':
            # Get children
            children = Student.query.filter_by(parent_id=user_id, is_active=True).all()
            
            children_data = []
            total_balance = 0
            
            for child in children:
                child_balance = child.get_total_fees_balance()
                total_balance += child_balance
                
                # Get recent grades
                recent_grades = Grade.query.filter_by(
                    student_id=child.id
                ).order_by(Grade.created_at.desc()).limit(5).all()
                
                children_data.append({
                    'id': child.id,
                    'full_name': child.full_name,
                    'admission_number': child.admission_number,
                    'current_class': child.current_class,
                    'fee_balance': child_balance,
                    'recent_grades_count': len(recent_grades)
                })
            
            dashboard_data.update({
                'children': children_data,
                'total_fee_balance': total_balance,
                'children_count': len(children)
            })
        
        # Get recent announcements
        target_audiences = ['all']
        if user.role == 'parent':
            target_audiences.append('parents')
        
        recent_announcements = Announcement.query.filter(
            Announcement.is_active == True,
            Announcement.target_audience.in_(target_audiences)
        ).order_by(Announcement.created_at.desc()).limit(5).all()
        
        announcements_data = []
        for announcement in recent_announcements:
            announcements_data.append({
                'id': announcement.id,
                'title': announcement.title,
                'priority': announcement.priority,
                'created_at': announcement.created_at.isoformat() if announcement.created_at else None
            })
        
        dashboard_data['recent_announcements'] = announcements_data
        
        return jsonify({
            'success': True,
            'dashboard': dashboard_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get dashboard data: {str(e)}'
        }), 500

@mobile_api.errorhandler(404)
def mobile_not_found(error):
    return jsonify({
        'success': False,
        'message': 'Endpoint not found'
    }), 404

@mobile_api.errorhandler(500)
def mobile_internal_error(error):
    return jsonify({
        'success': False,
        'message': 'Internal server error'
    }), 500
