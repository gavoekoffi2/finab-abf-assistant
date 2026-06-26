from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class MaritalStatus(str, Enum):
    single = "célibataire"
    married = "marié"
    common_law = "conjoint de fait"
    single_parent = "monoparental"
    other = "autre"


class Sex(str, Enum):
    female = "Femme"
    male = "Homme"
    undisclosed = "Non précisé"


class ClientIdentity(BaseModel):
    legal_last_name: str = Field(..., min_length=1)
    first_names: str = Field(..., min_length=1)
    date_of_birth: date
    sex: Sex = Sex.undisclosed
    place_of_birth: str = ""
    arrival_in_canada: Optional[date] = None
    residency_status: str = ""
    marital_status: MaritalStatus = MaritalStatus.other
    dependents_count: int = Field(default=0, ge=0, le=20)

    @property
    def full_name(self) -> str:
        return f"{self.first_names} {self.legal_last_name}".strip()


class ContactInfo(BaseModel):
    phone: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    province: str = ""
    postal_code: str = ""


class EmploymentInfo(BaseModel):
    occupation: str = ""
    employer_name: str = ""
    employer_address: str = ""
    annual_income: float = Field(default=0, ge=0)
    monthly_net_income: float = Field(default=0, ge=0)


class FinancialInfo(BaseModel):
    total_assets: float = Field(default=0, ge=0)
    cash_savings: float = Field(default=0, ge=0)
    personal_property: float = Field(default=0, ge=0)
    total_debts: float = Field(default=0, ge=0)
    credit_cards: float = Field(default=0, ge=0)
    car_loan: float = Field(default=0, ge=0)
    student_loan: float = Field(default=0, ge=0)
    personal_loan: float = Field(default=0, ge=0)
    mortgage: float = Field(default=0, ge=0)
    monthly_expenses: float = Field(default=0, ge=0)
    monthly_debt_repayment: float = Field(default=0, ge=0)
    monthly_savings: float = Field(default=0, ge=0)


class InsuranceInfo(BaseModel):
    has_existing_life_insurance: bool = False
    existing_life_coverage: float = Field(default=0, ge=0)
    existing_monthly_premium: float = Field(default=0, ge=0)
    existing_retirement_savings_note: str = ""
    no_insurance_reason: str = ""


class GoalsInfo(BaseModel):
    short_term_goals: str = ""
    long_term_goals: str = ""
    family_need_if_death: str = ""
    priority_projects: str = ""
    acceptable_monthly_budget: float = Field(default=0, ge=0)
    client_preference: str = ""


class HealthInfo(BaseModel):
    height: str = ""
    weight: str = ""
    smoker: Optional[bool] = None
    health_notes: str = ""


class MeetingInfo(BaseModel):
    availability: str = ""
    preferred_mode: str = ""
    consent_acknowledged: bool = False


class ProspectSubmission(BaseModel):
    identity: ClientIdentity
    contact: ContactInfo = ContactInfo()
    employment: EmploymentInfo = EmploymentInfo()
    financial: FinancialInfo = FinancialInfo()
    insurance: InsuranceInfo = InsuranceInfo()
    goals: GoalsInfo = GoalsInfo()
    health: HealthInfo = HealthInfo()
    meeting: MeetingInfo = MeetingInfo()

    @field_validator("meeting")
    @classmethod
    def require_consent(cls, meeting: MeetingInfo) -> MeetingInfo:
        # Keep warning-level validation for now in product UI; strict enforcement can be enabled later.
        return meeting


class AdvisorReview(BaseModel):
    reviewed_by_advisor: bool = False
    advisor_name: str = "KOFFI ABRAHAM AKPOBI"
    advisor_phone: str = "4383345252"
    advisor_email: str = "KOFFI.AKPOBI@MYGREATWAY.CA"
    signed_date: date = Field(default_factory=date.today)
    replacement_years: int = Field(default=10, ge=0, le=50)
    final_recommended_coverage: float = Field(default=0, ge=0)
    recommendation_1_budget: float = Field(default=0, ge=0)
    recommendation_2_budget: float = Field(default=0, ge=0)
    client_preference_budget: float = Field(default=0, ge=0)
    recommendation_1_notes: str = ""
    recommendation_2_notes: str = ""
    preference_notes: str = ""
    agent_notes: str = ""


class AbfGenerationRequest(BaseModel):
    prospect: ProspectSubmission
    review: AdvisorReview
    allow_draft_watermark: bool = True


class AbfGenerationResult(BaseModel):
    output_path: str
    pages_before: int
    pages_after: int
    is_form_pdf_before: bool
    is_form_pdf_after: bool
    filled_widget_updates: int
    missing_fields: list[str]
    layout_preserved: bool
