# analytics.py
from sqlalchemy import func, extract
from datetime import datetime
from collections import defaultdict
import json

class AnalyticsService:
    @staticmethod
    def get_student_analytics(student_id, db, Student, Grade, Subject, FeePayment):
        """Get detailed analytics for a specific student"""
        student = Student.query.get(student_id)
        if not student:
            return None
        
        current_year = datetime.now().year
        
        # Academic performance over time
        performance_trend = db.session.query(
            Grade.term,
            func.avg(Grade.percentage)
        ).filter_by(
            student_id=student_id,
            year=current_year
        ).group_by(Grade.term).all()
        
        # Subject-wise performance
        subject_performance = db.session.query(
            Subject.name,
            func.avg(Grade.percentage)
        ).join(Grade).filter(
            Grade.student_id == student_id,
            Grade.year == current_year
        ).group_by(Subject.name).all()
        
        # Fee payment history
        payment_history = db.session.query(
            extract('month', FeePayment.payment_date).label('month'),
            func.sum(FeePayment.amount_paid)
        ).filter(
            FeePayment.student_id == student_id,
            extract('year', FeePayment.payment_date) == current_year
        ).group_by('month').all()
        
        return {
            'student': {
                'name': student.full_name,
                'admission_number': student.admission_number,
                'class': student.current_class
            },
            'academic': {
                'performance_trend': dict(performance_trend),
                'subject_performance': dict(subject_performance)
            },
            'financial': {
                'payment_history': dict(payment_history),
                'current_balance': student.get_total_fees_balance()
            }
        }

    @staticmethod
    def get_school_statistics(db, Student, FeeStatement):
        """Get high-level statistics for the entire school"""
        # Total number of students
        total_students = db.session.query(Student).count()
        
        # Total fees due and paid
        total_fees_due = db.session.query(func.sum(FeeStatement.amount_due)).scalar() or 0
        total_fees_paid = db.session.query(func.sum(FeeStatement.total_paid)).scalar() or 0
        
        # Student enrollment by class
        enrollment_by_class = db.session.query(
            Student.class_level,
            func.count(Student.id)
        ).group_by(Student.class_level).order_by(Student.class_level).all()
        
        return {
            'total_students': total_students,
            'total_fees_due': total_fees_due,
            'total_fees_paid': total_fees_paid,
            'fees_balance': total_fees_due - total_fees_paid,
            'enrollment_by_class': dict(enrollment_by_class)
        }

analytics_service = AnalyticsService()