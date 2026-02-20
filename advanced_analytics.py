from sqlalchemy import func, case, and_, or_
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# ⚠️ Make sure you import your db and models:
#from models import db
from models import Student, Grade, Subject, FeePayment, FeeStatement

class AdvancedAnalytics:
    @staticmethod
    def get_performance_trends(student_id=None, class_name=None, subject_id=None):
        """Get detailed performance trends with statistical analysis"""
        query = db.session.query(
            Grade.term,
            Grade.year,
            func.avg(Grade.percentage).label('avg_percentage'),
            func.count(Grade.id).label('total_grades'),
            func.stddev(Grade.percentage).label('std_dev')
        )
        
        if student_id:
            query = query.filter(Grade.student_id == student_id)
        if class_name:
            # ✅ Fix: `current_class_id` is FK, not `current_class`
            query = query.join(Student).join(Class).filter(Class.name == class_name)
        if subject_id:
            query = query.filter(Grade.subject_id == subject_id)
        
        results = query.group_by(Grade.term, Grade.year).order_by(Grade.year, Grade.term).all()
        
        # Calculate trends
        trends = []
        for i, result in enumerate(results):
            trend_data = {
                'term': result.term,
                'year': result.year,
                'average': round(result.avg_percentage or 0, 2),
                'total_grades': result.total_grades,
                'std_deviation': round(result.std_dev or 0, 2),
                'improvement': 0
            }
            
            if i > 0:
                prev_avg = results[i-1].avg_percentage or 0
                trend_data['improvement'] = round((result.avg_percentage or 0) - prev_avg, 2)
            
            trends.append(trend_data)
        
        return trends
    
    @staticmethod
    def get_subject_performance_matrix():
        """Get performance matrix across all subjects and classes"""
        results = db.session.query(
            Subject.name.label('subject'),
            Class.name.label('class_name'),
            func.avg(Grade.percentage).label('avg_percentage'),
            func.count(Grade.id).label('student_count')
        ).join(Grade).join(Student).join(Class).group_by(
            Subject.name, Class.name
        ).all()
        
        # Convert to matrix format
        matrix = {}
        for result in results:
            if result.subject not in matrix:
                matrix[result.subject] = {}
            matrix[result.subject][result.class_name] = {
                'average': round(result.avg_percentage or 0, 2),
                'count': result.student_count
            }
        
        return matrix
    
    @staticmethod
    def get_fee_collection_analysis():
        """Detailed fee collection analysis"""
        current_year = datetime.now().year
        
        # Monthly collection trends
        monthly_data = db.session.query(
            func.extract('month', FeePayment.payment_date).label('month'),
            func.sum(FeePayment.amount_paid).label('total_collected'),
            func.count(FeePayment.id).label('payment_count'),
            func.avg(FeePayment.amount_paid).label('avg_payment')
        ).filter(
            func.extract('year', FeePayment.payment_date) == current_year
        ).group_by('month').all()
        
        # Collection efficiency by class
        class_efficiency = db.session.query(
            Class.name.label("class"),
            func.sum(FeeStatement.amount_due).label('total_due'),
            func.sum(FeePayment.amount_paid).label('total_paid'),
            (func.sum(FeePayment.amount_paid) / func.nullif(func.sum(FeeStatement.amount_due), 0) * 100).label('collection_rate')
        ).join(Student, Student.id == FeeStatement.student_id).join(Class, Student.current_class_id == Class.id).join(FeePayment, FeePayment.student_id == Student.id).group_by(Class.name).all()
        
        # Overdue analysis
        overdue_analysis = db.session.query(
            case(
                (FeeStatement.amount_due - func.coalesce(func.sum(FeePayment.amount_paid), 0) == 0, 'Fully Paid'),
                ((FeeStatement.amount_due - func.coalesce(func.sum(FeePayment.amount_paid), 0)) <= 5000, 'Low Balance'),
                ((FeeStatement.amount_due - func.coalesce(func.sum(FeePayment.amount_paid), 0)) <= 20000, 'Medium Balance'),
                else_='High Balance'
            ).label('balance_category'),
            func.count(FeeStatement.id).label('student_count'),
            (func.sum(FeeStatement.amount_due) - func.sum(FeePayment.amount_paid)).label('total_balance')
        ).outerjoin(FeePayment, FeePayment.student_id == FeeStatement.student_id).group_by('balance_category').all()
        
        return {
            'monthly_trends': [dict(row._mapping) for row in monthly_data],
            'class_efficiency': [dict(row._mapping) for row in class_efficiency],
            'overdue_analysis': [dict(row._mapping) for row in overdue_analysis]
        }
    
    @staticmethod
    def get_student_risk_assessment():
        """Identify students at risk based on academic and financial factors"""
        current_year = datetime.now().year
        current_term = "Term 1"  # TODO: Dynamically fetch current term
        
        # Academic risk factors
        academic_risk = db.session.query(
            Student.id,
            Student.full_name,
            Class.name.label("class"),
            func.avg(Grade.percentage).label('avg_performance'),
            func.count(Grade.id).label('grade_count')
        ).join(Grade).join(Class).filter(
            Grade.year == current_year,
            Grade.term == current_term
        ).group_by(Student.id, Class.name).having(
            func.avg(Grade.percentage) < 50  # Below 50% average
        ).all()
        
        # Financial risk factors
        financial_risk = db.session.query(
            Student.id,
            Student.full_name,
            func.sum(FeeStatement.amount_due - func.coalesce(FeePayment.amount_paid, 0)).label('total_balance')
        ).join(FeeStatement).outerjoin(FeePayment, FeePayment.student_id == Student.id).group_by(Student.id).having(
            func.sum(FeeStatement.amount_due - func.coalesce(FeePayment.amount_paid, 0)) > 20000
        ).all()
        
        # Combine risks
        risk_students = []
        academic_dict = {s.id: s for s in academic_risk}
        financial_dict = {s.id: s for s in financial_risk}
        
        all_risk_ids = set(academic_dict.keys()) | set(financial_dict.keys())
        
        for student_id in all_risk_ids:
            risk_factors = []
            if student_id in academic_dict:
                risk_factors.append('Academic')
            if student_id in financial_dict:
                risk_factors.append('Financial')
            
            student = Student.query.get(student_id)
            risk_students.append({
                'student_id': student_id,
                'name': student.full_name,
                'class': student.current_class.name if student.current_class else "N/A",
                'risk_factors': risk_factors,
                'academic_avg': getattr(academic_dict.get(student_id), "avg_performance", None),
                'outstanding_balance': getattr(financial_dict.get(student_id), "total_balance", 0)
            })
        
        return risk_students

advanced_analytics = AdvancedAnalytics()
