"""
Input validation schemas using Marshmallow
"""
from marshmallow import Schema, fields, validate, ValidationError, validates
import re


def validate_email(email: str) -> bool:
    """
    Validate email format
    Args:
        email: Email address to validate
    Returns:
        True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


class UserRegistrationSchema(Schema):
    """Schema for user registration validation"""
    email = fields.Email(required=True, error_messages={"required": "Email is required"})
    password = fields.String(required=True, validate=validate.Length(min=8, max=128))
    name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    purpose = fields.String(required=True, validate=validate.OneOf([
        'high_school', 'exam_prep', 'after_tenth'
    ]))
    institution_id = fields.String(allow_none=True)
    
    @validates('password')
    def validate_password(self, value):
        """Validate password strength"""
        if not re.search(r'[A-Z]', value):
            raise ValidationError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', value):
            raise ValidationError("Password must contain at least one lowercase letter")
        if not re.search(r'\d', value):
            raise ValidationError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise ValidationError("Password must contain at least one special character")


class UserLoginSchema(Schema):
    """Schema for user login validation"""
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=1))


class ChapterProgressSchema(Schema):
    """Schema for chapter progress updates"""
    subject = fields.String(required=True, validate=validate.Length(min=1, max=100))
    chapter = fields.String(required=True, validate=validate.Length(min=1, max=200))
    completed = fields.Boolean(required=True)


class GoalSchema(Schema):
    """Schema for goal creation/updates"""
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String(validate=validate.Length(max=1000))
    target_date = fields.Date(required=True)
    priority = fields.String(validate=validate.OneOf(['low', 'medium', 'high']))


class TaskSchema(Schema):
    """Schema for task creation/updates"""
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String(validate=validate.Length(max=1000))
    due_date = fields.Date(allow_none=True)
    priority = fields.String(validate=validate.OneOf(['low', 'medium', 'high']))
    subject = fields.String(validate=validate.Length(max=100))


class StudySessionSchema(Schema):
    """Schema for study session logging"""
    subject = fields.String(required=True)
    duration_minutes = fields.Integer(required=True, validate=validate.Range(min=1, max=480))
    notes = fields.String(validate=validate.Length(max=500))


class TestResultSchema(Schema):
    """Schema for test result entry"""
    test_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    subject = fields.String(required=True)
    score = fields.Float(required=True, validate=validate.Range(min=0, max=100))
    max_score = fields.Float(required=True, validate=validate.Range(min=1))
    test_date = fields.Date(required=True)
    notes = fields.String(validate=validate.Length(max=500))


class InstitutionJoinSchema(Schema):
    """Schema for joining an institution"""
    invite_code = fields.String(required=True, validate=validate.Length(min=6, max=20))


class BroadcastMessageSchema(Schema):
    """Schema for broadcast messages"""
    message = fields.String(required=True, validate=validate.Length(min=1, max=1000))
    target_class = fields.String(allow_none=True)


class ProfileEditSchema(Schema):
    """Schema for profile updates"""
    name = fields.String(validate=validate.Length(min=2, max=100))
    bio = fields.String(validate=validate.Length(max=500))
    phone = fields.String(validate=validate.Regexp(r'^[\d\s\-\+\(\)]+$', error="Invalid phone number"))
    
    @validates('phone')
    def validate_phone(self, value):
        if value:
            digits = re.sub(r'\D', '', value)
            if len(digits) < 10 or len(digits) > 15:
                raise ValidationError("Phone number must have 10-15 digits")


# Instantiate schemas for reuse
user_registration_schema = UserRegistrationSchema()
user_login_schema = UserLoginSchema()
chapter_progress_schema = ChapterProgressSchema()
goal_schema = GoalSchema()
task_schema = TaskSchema()
study_session_schema = StudySessionSchema()
test_result_schema = TestResultSchema()
institution_join_schema = InstitutionJoinSchema()
broadcast_message_schema = BroadcastMessageSchema()
profile_edit_schema = ProfileEditSchema()


def validate_schema(schema, data):
    """
    Helper function to validate data against a schema
    Args:
        schema: Marshmallow schema instance
        data: Data to validate
    Returns:
        Tuple of (is_valid, errors_or_result)
    """
    try:
        result = schema.load(data)
        return True, result
    except ValidationError as err:
        return False, err.messages
