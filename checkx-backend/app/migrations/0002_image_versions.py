from uuid import uuid4

from tortoise import fields, migrations
from tortoise.fields.base import OnDelete
from tortoise.migrations import operations as ops


class Migration(migrations.Migration):
    dependencies = [("models", "0001_initial")]

    initial = False

    operations = [
        ops.CreateModel(
            name="DesignImageVersion",
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
                        related_name="image_versions",
                        on_delete=OnDelete.CASCADE,
                    ),
                ),
                ("version", fields.IntField()),
                ("name", fields.CharField(max_length=180)),
                ("notes", fields.TextField(default="", unique=False)),
                ("stored_name", fields.CharField(unique=True, max_length=80)),
                ("original_name", fields.CharField(max_length=255)),
                ("mime_type", fields.CharField(max_length=40)),
                ("size", fields.BigIntField()),
                ("width", fields.IntField()),
                ("height", fields.IntField()),
                ("archived_at", fields.DatetimeField(auto_now=False, auto_now_add=True)),
            ],
            options={
                "table": "designimageversion",
                "app": "models",
                "unique_together": (("design", "version"),),
                "pk_attr": "id",
            },
            bases=["Model"],
        ),
        ops.AddField(
            model_name="Design",
            name="version",
            field=fields.IntField(default=1, db_default=1),
        ),
        ops.AddField(
            model_name="Review",
            name="version",
            field=fields.IntField(default=1, db_default=1),
        ),
    ]
