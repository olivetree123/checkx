from tortoise import fields, models


class User(models.Model):
    id = fields.UUIDField(primary_key=True)
    email = fields.CharField(max_length=254, unique=True)
    display_name = fields.CharField(max_length=80)
    password_hash = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)


class Credential(models.Model):
    id = fields.UUIDField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="credentials", on_delete=fields.CASCADE
    )
    token_hash = fields.CharField(max_length=64, unique=True)
    kind = fields.CharField(max_length=16)
    name = fields.CharField(max_length=80, default="Browser")
    expires_at = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True)


class Project(models.Model):
    id = fields.UUIDField(primary_key=True)
    owner = fields.ForeignKeyField("models.User", related_name="projects", on_delete=fields.CASCADE)
    name = fields.CharField(max_length=120)
    description = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class Page(models.Model):
    id = fields.UUIDField(primary_key=True)
    project = fields.ForeignKeyField(
        "models.Project", related_name="pages", on_delete=fields.CASCADE
    )
    name = fields.CharField(max_length=120)
    description = fields.TextField(default="")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class Design(models.Model):
    id = fields.UUIDField(primary_key=True)
    page = fields.ForeignKeyField("models.Page", related_name="designs", on_delete=fields.CASCADE)
    name = fields.CharField(max_length=180)
    notes = fields.TextField(default="")
    stored_name = fields.CharField(max_length=80, unique=True)
    original_name = fields.CharField(max_length=255)
    mime_type = fields.CharField(max_length=40)
    size = fields.BigIntField()
    width = fields.IntField()
    height = fields.IntField()
    version = fields.IntField(default=1, db_default=1)
    status = fields.CharField(max_length=24, default="pending")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class DesignImageVersion(models.Model):
    # Archived images. The current image stays on Design.

    id = fields.UUIDField(primary_key=True)
    design = fields.ForeignKeyField(
        "models.Design", related_name="image_versions", on_delete=fields.CASCADE
    )
    version = fields.IntField()
    name = fields.CharField(max_length=180)
    notes = fields.TextField(default="")
    stored_name = fields.CharField(max_length=80, unique=True)
    original_name = fields.CharField(max_length=255)
    mime_type = fields.CharField(max_length=40)
    size = fields.BigIntField()
    width = fields.IntField()
    height = fields.IntField()
    archived_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        unique_together = (("design", "version"),)


class Review(models.Model):
    id = fields.UUIDField(primary_key=True)
    design = fields.ForeignKeyField(
        "models.Design", related_name="reviews", on_delete=fields.CASCADE
    )
    author_label = fields.CharField(max_length=80)
    content = fields.TextField()
    version = fields.IntField(default=1, db_default=1)
    status = fields.CharField(max_length=24)
    created_at = fields.DatetimeField(auto_now_add=True)
