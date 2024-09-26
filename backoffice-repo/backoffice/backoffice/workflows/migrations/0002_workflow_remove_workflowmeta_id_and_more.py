# Generated by Django 4.2.6 on 2023-10-17 07:16

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Workflow",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("data", models.JSONField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PREPROCESSING", "Preprocessing"),
                            ("APPROVAL", "Approval"),
                            ("POSTPROCESSING", "Postprocessing"),
                        ],
                        default="PREPROCESSING",
                        max_length=30,
                    ),
                ),
                ("core", models.BooleanField()),
                ("is_update", models.BooleanField()),
            ],
        ),
        migrations.RemoveField(
            model_name="workflowmeta",
            name="id",
        ),
        migrations.RemoveField(
            model_name="workflowstatus",
            name="id",
        ),
        migrations.DeleteModel(
            name="WorkflowData",
        ),
        migrations.DeleteModel(
            name="WorkflowMeta",
        ),
        migrations.DeleteModel(
            name="WorkflowStatus",
        ),
    ]
