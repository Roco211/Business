from pydantic import BaseModel


class CreateMediaUploadRequest(BaseModel):
    media_type: str
    file_name: str
    content_type: str
    size_bytes: int


class CreateMediaUploadData(BaseModel):
    media_id: str
    upload_url: str
    public_url: str


class CompleteMediaUploadRequest(BaseModel):
    checksum_sha256: str
    size_bytes: int


class CompleteMediaUploadData(BaseModel):
    media_id: str
    status: str
