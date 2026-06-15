# Django
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("eveonline", "0025_remove_evecharacter_last_updated_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="General",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                )
            ],
            options={
                "managed": False,
                "default_permissions": (),
                "permissions": [("view_pi", "Can access PI Tracker")],
            },
        ),
        migrations.CreateModel(
            name="PiOwner",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pi_owners",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "character",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pi_owner",
                        to="eveonline.evecharacter",
                    ),
                ),
            ],
            options={"ordering": ["character__character_name"]},
        ),
        migrations.CreateModel(
            name="PiPlanet",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("planet_id", models.IntegerField()),
                ("planet_name", models.CharField(default="", max_length=100)),
                (
                    "planet_type",
                    models.CharField(
                        choices=[
                            ("temperate", "Temperate"),
                            ("barren", "Barren"),
                            ("oceanic", "Oceanic"),
                            ("ice", "Ice"),
                            ("gas", "Gas"),
                            ("lava", "Lava"),
                            ("storm", "Storm"),
                            ("plasma", "Plasma"),
                        ],
                        default="barren",
                        max_length=20,
                    ),
                ),
                ("upgrade_level", models.IntegerField(default=0)),
                ("last_update", models.DateTimeField(blank=True, null=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="planets",
                        to="aa_pi_tracker.piowner",
                    ),
                ),
            ],
            options={
                "ordering": ["owner__character__character_name", "planet_name"],
                "unique_together": {("owner", "planet_id")},
            },
        ),
        migrations.CreateModel(
            name="PiExtractorPin",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("product_type_id", models.IntegerField()),
                ("product_name", models.CharField(default="", max_length=100)),
                ("cycle_time", models.IntegerField(default=1800)),
                ("qty_per_cycle", models.IntegerField(default=0)),
                ("expiry_time", models.DateTimeField(blank=True, null=True)),
                ("install_time", models.DateTimeField(blank=True, null=True)),
                ("last_cycle_start", models.DateTimeField(blank=True, null=True)),
                (
                    "planet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="extractors",
                        to="aa_pi_tracker.piplanet",
                    ),
                ),
            ],
            options={"ordering": ["planet", "product_name"]},
        ),
        migrations.CreateModel(
            name="PiFactoryPin",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("schematic_id", models.IntegerField(default=0)),
                ("schematic_name", models.CharField(default="", max_length=100)),
                (
                    "planet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="factories",
                        to="aa_pi_tracker.piplanet",
                    ),
                ),
            ],
            options={"ordering": ["planet", "schematic_name"]},
        ),
        migrations.CreateModel(
            name="PiProject",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="projects",
                        to="aa_pi_tracker.piowner",
                    ),
                ),
            ],
            options={"ordering": ["owner", "name"]},
        ),
        migrations.CreateModel(
            name="PiProjectObjective",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("schematic_name", models.CharField(max_length=100)),
                ("target_qty_per_hour", models.IntegerField(default=1)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="objectives",
                        to="aa_pi_tracker.piproject",
                    ),
                ),
            ],
            options={
                "ordering": ["schematic_name"],
                "unique_together": {("project", "schematic_name")},
            },
        ),
        migrations.CreateModel(
            name="PiProjectPlanet",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assigned_planets",
                        to="aa_pi_tracker.piproject",
                    ),
                ),
                (
                    "planet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_links",
                        to="aa_pi_tracker.piplanet",
                    ),
                ),
            ],
            options={
                "ordering": ["planet__planet_name"],
                "unique_together": {("project", "planet")},
            },
        ),
    ]
