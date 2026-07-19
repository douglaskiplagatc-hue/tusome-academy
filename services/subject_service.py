# services/subject_service.py
import json
from typing import List, Dict, Optional
from models import Subject, Student, Class, db

class SubjectService:
    """Service to manage subjects based on grade level"""

    def __init__(self):
        self.subjects_data = self._load_subjects_data()

    def _load_subjects_data(self):
        """Load subjects from JSON file"""
        with open('data/subjects.json', 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_subjects_for_grade(self, grade: int) -> Dict:
        """Get all subjects for a specific grade level"""
        if 1 <= grade <= 6:
            return self.subjects_data['subjects']['primary']
        elif 7 <= grade <= 9:
            return self.subjects_data['subjects']['junior_secondary']
        elif 10 <= grade <= 12:
            return self.subjects_data['subjects']['senior_secondary']
        else:
            return {}

    def get_core_subjects(self, grade: int) -> List[Dict]:
        """Get core subjects for a grade level"""
        subjects = self.get_subjects_for_grade(grade)

        if 1 <= grade <= 6:
            return subjects.get('compulsory', [])
        elif 7 <= grade <= 9:
            return subjects.get('core', [])
        else:
            # For senior secondary, need pathway
            return []

    def get_elective_subjects(self, grade: int, pathway: str = None) -> List[Dict]:
        """Get elective subjects based on grade and optional pathway"""
        subjects = self.get_subjects_for_grade(grade)

        if 7 <= grade <= 9:
            electives = subjects.get('electives', {})
            if pathway and pathway in electives:
                return electives[pathway]
            # Return all electives if no pathway specified
            all_electives = []
            for category in electives.values():
                all_electives.extend(category)
            return all_electives
        elif 10 <= grade <= 12:
            pathways = subjects.get('pathways', {})
            if pathway and pathway in pathways:
                return pathways[pathway].get('subjects', [])
            return []
        else:
            return []

    def get_subjects_by_pathway(self, grade: int, pathway: str) -> List[Dict]:
        """Get subjects for a specific senior secondary pathway"""
        if grade >= 10:
            subjects = self.get_subjects_for_grade(grade)
            pathways = subjects.get('pathways', {})
            if pathway in pathways:
                return pathways[pathway].get('subjects', [])
        return []

    def get_available_pathways(self, grade: int) -> Dict:
        """Get available pathways for senior secondary"""
        if grade >= 10:
            subjects = self.get_subjects_for_grade(grade)
            pathways = subjects.get('pathways', {})
            return {key: value.get('description', key) for key, value in pathways.items()}
        return {}

    def create_subjects_for_class(self, class_obj: Class, pathway: str = None):
        """Create all required subjects for a class"""
        grade = class_obj.grade_level
        subjects_data = self.get_subjects_for_grade(grade)

        created_subjects = []

        # Create core subjects
        if 1 <= grade <= 6:
            core_subjects = subjects_data.get('compulsory', [])
        elif 7 <= grade <= 9:
            core_subjects = subjects_data.get('core', [])
        else:
            core_subjects = []

        for subject_data in core_subjects:
            subject = Subject.query.filter_by(
                code=subject_data['code'],
                class_id=class_obj.id
            ).first()

            if not subject:
                subject = Subject(
                    code=subject_data['code'],
                    name=subject_data['name'],
                    level=f'Grade {grade}',
                    compulsory=True,
                    class_id=class_obj.id,
                    category=subject_data.get('category', 'Core'),
                    cbc_level=subject_data.get('cbc_level', 'Primary')
                )
                db.session.add(subject)
                created_subjects.append(subject)

        # Create elective subjects for junior secondary
        if 7 <= grade <= 9 and pathway:
            elective_subjects = self.get_elective_subjects(grade, pathway)
            for subject_data in elective_subjects:
                subject = Subject.query.filter_by(
                    code=subject_data['code'],
                    class_id=class_obj.id
                ).first()

                if not subject:
                    subject = Subject(
                        code=subject_data['code'],
                        name=subject_data['name'],
                        level=f'Grade {grade}',
                        compulsory=False,
                        class_id=class_obj.id,
                        category=subject_data.get('category', 'Elective'),
                        cbc_level='JuniorSecondary'
                    )
                    db.session.add(subject)
                    created_subjects.append(subject)

        # Create senior secondary pathway subjects
        elif grade >= 10 and pathway:
            pathway_subjects = self.get_subjects_by_pathway(grade, pathway)
            for subject_data in pathway_subjects:
                subject = Subject.query.filter_by(
                    code=subject_data['code'],
                    class_id=class_obj.id
                ).first()

                if not subject:
                    subject = Subject(
                        code=subject_data['code'],
                        name=subject_data['name'],
                        level=f'Grade {grade}',
                        compulsory=subject_data.get('category') == 'Core',
                        class_id=class_obj.id,
                        category=subject_data.get('category', pathway),
                        cbc_level='SeniorSecondary'
                    )
                    db.session.add(subject)
                    created_subjects.append(subject)

        db.session.commit()
        return created_subjects

    def get_teacher_subjects(self, teacher_id: int, grade: int = None) -> List[Subject]:
        """Get subjects assigned to a teacher filtered by grade"""
        query = Subject.query.filter_by(teacher_id=teacher_id)
        if grade:
            query = query.filter(Subject.level.like(f'%{grade}%'))
        return query.all()

    def get_student_subjects(self, student_id: int) -> List[Dict]:
        """Get subjects for a student based on their class and pathway"""
        student = Student.query.get(student_id)
        if not student or not student.current_class:
            return []

        class_obj = student.current_class
        subjects = Subject.query.filter_by(class_id=class_obj.id).all()

        return [{
            'id': s.id,
            'code': s.code,
            'name': s.name,
            'category': s.category,
            'compulsory': s.compulsory
        } for s in subjects]
