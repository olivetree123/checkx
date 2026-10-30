from uuid import uuid4

from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True),
                ),
                ("email", fields.CharField(unique=True, max_length=254)),
                ("display_name", fields.CharField(max_length=80)),
                ("password_hash", fields.CharField(max_length=255)),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={"table": "user", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Credential",
            fields=[
                (
                    "id",
                    fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True),
                ),
                (
                    "user",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="user_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="credentials",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("token_hash", fields.CharField(unique=True, max_length=64)),
                ("kind", fields.CharField(max_length=16)),
                ("name", fields.CharField(default="Browser", max_length=80)),
                ("expires_at", fields.DatetimeField(auto_now=False, auto_now_add=False)),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={"table": "credential", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Project",
            fields=[
                (
                    "id",
                    fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True),
                ),
                (
                    "owner",
                    fields.ForeignKeyField(
                        "models.User",
                        source_field="owner_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="projects",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("name", fields.CharField(max_length=120)),
                ("description", fields.TextField(default="", unique=False)),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ("updated_at", fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={"table": "project", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Page",
            fields=[
                (
                    "id",
                    fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True),
                ),
                (
                    "project",
                    fields.ForeignKeyField(
                        "models.Project",
                        source_field="project_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="pages",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("name", fields.CharField(max_length=120)),
                ("description", fields.TextField(default="", unique=False)),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ("updated_at", fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={"table": "page", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Design",
            fields=[
                (
                    "id",
                    fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True),
                ),
                (
                    "page",
                    fields.ForeignKeyField(
                        "models.Page",
                        source_field="page_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="designs",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("name", fields.CharField(max_length=180)),
                ("notes", fields.TextField(default="", unique=False)),
                ("stored_name", fields.CharField(unique=True, max_length=80)),
                ("original_name", fields.CharField(max_length=255)),
                ("mime_type", fields.CharField(max_length=40)),
                ("size", fields.BigIntField()),
                ("width", fields.IntField()),
                ("height", fields.IntField()),
                ("status", fields.CharField(default="pending", max_length=24)),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
                ("updated_at", fields.DatetimeField(auto_now=True, auto_now_add=False)),
            ],
            options={"table": "design", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
        ops.CreateModel(
            name="Review",
            fields=[
                (
                    "id",
                    fields.UUIDField(primary_key=True, default=uuid4, unique=True, db_index=True),
                ),
                (
                    "design",
                    fields.ForeignKeyField(
                        "models.Design",
                        source_field="design_id",
                        db_constraint=True,
                        to_field="id",
                        related_name="reviews",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("author_label", fields.CharField(max_length=80)),
                ("content", fields.TextField(unique=False)),
                ("status", fields.CharField(max_length=24)),
                ("created_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={"table": "review", "app": "models", "pk_attr": "id"},
            bases=["Model"],
        ),
    ]
