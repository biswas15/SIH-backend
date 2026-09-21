from typing import Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

class LocationContext(BaseModel):
    """
    Provider-neutral representation of a location for heat risk assessment.
    """
    latitude: float = Field(..., description="Latitude of the location")
    longitude: float = Field(..., description="Longitude of the location")
    
    # Administrative context
    country: Optional[str] = Field(None, description="Country name")
    state: Optional[str] = Field(None, description="State or province name")
    district: Optional[str] = Field(None, description="District or county name")
    city: Optional[str] = Field(None, description="City or municipality name")
    locality: Optional[str] = Field(None, description="Locality, ward, or neighborhood name")
    
    # Identifiers and Metadata
    spatial_id: Optional[str] = Field(None, description="Provider-specific or internal spatial identifier (e.g. H01)")
    provider: str = Field(..., description="Name of the location provider")
    provider_metadata: dict = Field(default_factory=dict, description="Any additional metadata from the provider")
