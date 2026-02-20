# reports.py
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

class ReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
    
    def generate_student_report_card(self, student, term, year):
        """Generate comprehensive report card PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Header
        title = Paragraph(f"TUSOME ACADEMY<br/>STUDENT REPORT CARD", self.title_style)
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Student Information
        student_info = [
            ['Student Name:', student.full_name],
            ['Admission Number:', student.admission_number],
            ['Class:', student.current_class],
            ['Term:', f"{term} {year}"],
            ['Date Generated:', datetime.now().strftime('%Y-%m-%d')]
        ]
        
        student_table = Table(student_info, colWidths=[2*inch, 3*inch])
        student_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(student_table)
        story.append(Spacer(1, 20))
        
        # Grades Table
        grades = Grade.query.filter_by(
            student_id=student.id, 
            term=term, 
            year=year
        ).join(Subject).all()
        
        if grades:
            grade_data = [['Subject', 'Marks', 'Grade', 'Points', 'Comment']]
            total_points = 0
            
            for grade in grades:
                grade_data.append([
                    grade.subject.name,
                    f"{grade.marks}/{grade.max_marks}",
                    grade.grade_letter,
                    str(grade.points),
                    grade.teacher_comment or 'Good work'
                ])
                total_points += grade.points
            
            # Calculate average
            average_points = total_points / len(grades) if grades else 0
            grade_data.append(['AVERAGE', '', '', f"{average_points:.1f}", ''])
            
            grade_table = Table(grade_data, colWidths=[2*inch, 1*inch, 0.8*inch, 0.8*inch, 2.4*inch])
            grade_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(Paragraph("ACADEMIC PERFORMANCE", self.styles['Heading2']))
            story.append(Spacer(1, 12))
            story.append(grade_table)
        
        # Generate PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def generate_fee_statement(self, student, year):
        """Generate fee statement PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Header
        title = Paragraph(f"TUSOME ACADEMY<br/>FEE STATEMENT", self.title_style)
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Student Information
        student_info = [
            ['Student Name:', student.full_name],
            ['Admission Number:', student.admission_number],
            ['Class:', student.current_class],
            ['Academic Year:', str(year)],
            ['Statement Date:', datetime.now().strftime('%Y-%m-%d')]
        ]
        
        student_table = Table(student_info, colWidths=[2*inch, 3*inch])
        student_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        story.append(student_table)
        story.append(Spacer(1, 20))
        
        # Fee Details
        fees = FeeStatement.query.filter_by(student_id=student.id, year=year).all()
        
        if fees:
            fee_data = [['Fee Type', 'Term', 'Amount Due', 'Amount Paid', 'Balance', 'Status']]
            total_due = 0
            total_paid = 0
            total_balance = 0
            
            for fee in fees:
                status = 'PAID' if fee.is_paid else 'OVERDUE' if fee.is_overdue else 'PENDING'
                fee_data.append([
                    fee.fee_type,
                    fee.term,
                    f"KES {fee.amount_due:,.2f}",
                    f"KES {fee.amount_paid:,.2f}",
                    f"KES {fee.balance:,.2f}",
                    status
                ])
                total_due += fee.amount_due
                total_paid += fee.amount_paid
                total_balance += fee.balance
            
            # Totals row
            fee_data.append([
                'TOTAL', '', 
                f"KES {total_due:,.2f}",
                f"KES {total_paid:,.2f}",
                f"KES {total_balance:,.2f}",
                ''
            ])
            
            fee_table = Table(fee_data, colWidths=[1.5*inch, 1*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1*inch])
            fee_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(Paragraph("FEE DETAILS", self.styles['Heading2']))
            story.append(Spacer(1, 12))
            story.append(fee_table)
        
        doc.build(story)
        buffer.seek(0)
        return buffer

report_generator = ReportGenerator()
