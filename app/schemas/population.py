from typing import Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

class PopulationContext(BaseModel):
    """
    Provider-neutral representation of demographic data for a location.
    """
    population: Optional[int] = Field(None, description="Total population estimate")
    density: Optional[float] = Field(None, description="Population density (persons per sq km)")
    area_km2: Optional[float] = Field(None, description="Total area in square kilometers")
    
    # Metadata
    data_year: Optional[int] = Field(None, description="Year of the population dataset")
    provider: str = Field(..., description="Provider of the population data")
    confidence_status: str = Field(default="provisional", description="Status/confidence level of the data")
    provider_metadata: dict = Field(default_factory=dict, description="Additional provider metadata")
