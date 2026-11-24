"""Import every model so Base.metadata is complete (needed by Alembic)."""
from app.models.applications import (  # noqa: F401
    STATUSES,
    ApplicationEvent,
    Interview,
    JobApplication,
    RecruiterContact,
)
from app.models.documents import ApplicationAnswer, CoverLetter, Document, GeneratedCV  # noqa: F401
from app.models.jobs import JobListing, JobMatch, JobRequirement, JobSource  # noqa: F401
from app.models.profile import (  # noqa: F401
    Certification,
    Education,
    Employment,
    LanguageSkill,
    Profile,
    Skill,
)
from app.models.system import (  # noqa: F401
    AgentActivityLog,
    AutomationSchedule,
    EmailDraft,
    Notification,
    UserSetting,
)
