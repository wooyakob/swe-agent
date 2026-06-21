from typing import List
from pydantic import BaseModel, Field


class POCStep(BaseModel):
    poc_step: str = Field(
        description="A single concrete step to create or modify this POC artifact, e.g. write a specific function, section, or code block"
    )
    additional_context: str = Field(
        "",
        description="Couchbase SDK patterns, API details, or feature specifics relevant to completing this step"
    )


class POCArtifact(BaseModel):
    file_path: str = Field(
        description="Full file path for this artifact (e.g. ./poc_workspace/app.py, ./poc_workspace/discovery_questions.md)"
    )
    artifact_description: str = Field(
        description="What this artifact is, what it demonstrates, and its purpose in the SE engagement"
    )
    poc_steps: List[POCStep] = Field(
        description="Ordered concrete steps to create this artifact"
    )


class SEEngagementPlan(BaseModel):
    customer_summary: str = Field(
        description="Concise summary of the customer's industry, use case, pain points, and key requirements"
    )
    relevant_couchbase_features: List[str] = Field(
        description="Couchbase features and products most relevant to this customer's needs"
    )
    artifacts: List[POCArtifact] = Field(
        description="Ordered list of deliverable artifacts to produce for this engagement"
    )
