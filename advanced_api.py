from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import io

advanced_api = Blueprint('advanced_api', __name__, url_prefix='/api/advanced')

@advanced_api.route('/analytics/performance-trends')
@login_required
def get_performance_trends():
    """Get performance trends with filters"""
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Access denied'}), 403
    
    student_id = request.args.get('student_id', type=int)
    class_name = request.args.get('class')
    subject_id = request.args.get('subject_id', type=int)
    
    trends = advanced_analytics.get_performance_trends(student_id, class_name, subject_id)
    return jsonify({'trends': trends})

@advanced_api.route('/analytics/subject-matrix')
@login_required
def get_subject_matrix():
    """Get subject performance matrix"""
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Access denied'}), 403
    
    matrix = advanced_analytics.get_subject_performance_matrix()
    return jsonify({'matrix': matrix})

@advanced_api.route('/analytics/fee-analysis')
@login_required
def get_fee_analysis():
    """Get detailed fee collection analysis"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    analysis = advanced_analytics.get_fee_collection_analysis()
    return jsonify(analysis)

@advanced_api.route('/analytics/risk-assessment')
@login_required
def get_risk_assessment():
    """Get student risk assessment"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    risk_students = advanced_analytics.get_student_risk_assessment()
    return jsonify({'risk_students': risk_students})

@advanced_api.route('/bulk/import-students', methods=['POST'])
@login_required
def bulk_import_students():
    """Bulk import students from CSV"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be CSV format'}), 400
    
    try:
        csv_content = file.read().decode('utf-8')
        result = bulk_operations.import_students_from_csv(csv_content)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Import failed: {str(e)}'}), 500

@advanced_api.route('/bulk/import-grades', methods=['POST'])
@login_required
def bulk_import_grades():
    """Bulk import grades from CSV"""
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Access denied'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be CSV format'}), 400
    
    try:
        csv_content = file.read().decode('utf-8')
        result = bulk_operations.import_grades_from_csv(csv_content)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Import failed: {str(e)}'}), 500

@advanced_api.route('/bulk/export-students')
@login_required
def bulk_export_students():
    """Export all students to CSV"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        csv_data = bulk_operations.export_students_to_csv()
        
        output = io.BytesIO()
        output.write(csv_data.encode('utf-8'))
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'students_export_{datetime.now().strftime("%Y%m%d")}.csv'
        )
    except Exception as e:
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime
import io

# Import the service classes
from advanced_analytics import AdvancedAnalytics
from bulk_operations import BulkOperations
from audit_logs import AuditLog, AuditLogger


# Create the Blueprint
advanced_api = Blueprint('advanced_api', __name__, url_prefix='/api/advanced')

# Analytics Endpoints
@advanced_api.route('/analytics/performance-trends')
@login_required
def get_performance_trends():
    """Get performance trends with filters"""
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Access denied'}), 403
    
    student_id = request.args.get('student_id', type=int)
    class_name = request.args.get('class')
    subject_id = request.args.get('subject_id', type=int)
    
    trends = AdvancedAnalytics.get_performance_trends(student_id, class_name, subject_id)
    return jsonify({'trends': trends})

@advanced_api.route('/analytics/subject-matrix')
@login_required
def get_subject_matrix():
    """Get subject performance matrix"""
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Access denied'}), 403
    
    matrix = AdvancedAnalytics.get_subject_performance_matrix()
    return jsonify({'matrix': matrix})

@advanced_api.route('/analytics/fee-analysis')
@login_required
def get_fee_analysis():
    """Get detailed fee collection and projection analysis"""
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Access denied'}), 403
    
    analysis = AdvancedAnalytics.get_fee_analysis()
    return jsonify({'analysis': analysis})

@advanced_api.route('/analytics/at-risk-students')
@login_required
def get_at_risk_students():
    """Get students identified as at risk (academic or financial)"""
    if current_user.role not in ['admin', 'teacher']:
        return jsonify({'error': 'Access denied'}), 403
    
    students = AdvancedAnalytics.get_at_risk_students()
    return jsonify({'students': students})


# Bulk Operations Endpoints
@advanced_api.route('/bulk/import-students', methods=['POST'])
@login_required
def bulk_import_students():
    """Import students from a CSV file"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.csv'):
        return jsonify({'error': 'No selected file or invalid file type'}), 400
    
    try:
        df = BulkOperations.import_students_from_csv(file)
        result = {'message': f'Successfully imported {len(df)} students.'}
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Import failed: {str(e)}'}), 500

@advanced_api.route('/bulk/export-students')
@login_required
def bulk_export_students():
    """Export all students to CSV"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        csv_data = BulkOperations.export_students_to_csv()
        
        output = io.BytesIO()
        output.write(csv_data.encode('utf-8'))
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'students_export_{datetime.now().strftime("%Y%m%d")}.csv'
        )
    except Exception as e:
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

# Audit Logs Endpoint
@advanced_api.route('/audit-logs')
@login_required
def get_audit_logs():
    """Get audit logs with pagination"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    table_name = request.args.get('table')
    action = request.args.get('action')
    
    # Use the static method from the AuditLogs class to handle the query
    logs, total_pages = AuditLogs.get_paginated_logs(page, per_page, table_name, action)
    
    return jsonify({
        'logs': logs,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages
    })
