"""Carry every existing account into the multi-role world.

Two things happen here, and both have to happen together:

* ``PARENT`` becomes ``OTA-ONA``. The role is the same role — the code is what
  changed, because role names are shown untranslated and the interface calls
  that role OTA-ONA in all three languages.
* Every account gets a ``UserRole`` row for the role it already held, so the
  single-role column and the new table agree from the first request after
  deploy. An account whose role means nothing to the new vocabulary (there
  should be none) becomes ``STAFF`` rather than a login that can see nothing.

Reversible: the down path folds the roles back onto the column and renames
OTA-ONA back to PARENT, so a rollback leaves a working single-role database.
"""
from django.db import migrations

#: Roles that existed before this migration, in the values they were stored as.
LEGACY_PARENT = "PARENT"
NEW_PARENT = "OTA-ONA"
KNOWN_ROLES = {
    "DEVELOPER",
    "SUPER_ADMIN",
    "MODERATOR",
    "ADMIN",
    "TEACHER",
    "CURATOR",
    "STAFF",
    NEW_PARENT,
}
DEFAULT_ROLE = "STAFF"

#: Rank, most privileged last — used to pick an active role on the way back.
RANK = {
    NEW_PARENT: 0,
    "STAFF": 1,
    "CURATOR": 2,
    "TEACHER": 3,
    "ADMIN": 4,
    "MODERATOR": 5,
    "SUPER_ADMIN": 6,
    "DEVELOPER": 7,
}


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserRole = apps.get_model("accounts", "UserRole")

    User.objects.filter(role=LEGACY_PARENT).update(role=NEW_PARENT)

    rows = []
    for user in User.objects.all().iterator():
        role = user.role if user.role in KNOWN_ROLES else DEFAULT_ROLE
        if role != user.role:
            User.objects.filter(pk=user.pk).update(role=role)
        rows.append(UserRole(user_id=user.pk, role=role))

    # ``ignore_conflicts`` so re-running on a half-migrated database is safe.
    UserRole.objects.bulk_create(rows, ignore_conflicts=True, batch_size=500)


def backwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserRole = apps.get_model("accounts", "UserRole")

    for user in User.objects.all().iterator():
        roles = list(
            UserRole.objects.filter(user_id=user.pk).values_list("role", flat=True)
        )
        if roles:
            best = max(roles, key=lambda role: RANK.get(role, -1))
            if best != user.role:
                User.objects.filter(pk=user.pk).update(role=best)

    User.objects.filter(role=NEW_PARENT).update(role=LEGACY_PARENT)
    UserRole.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_role_userrole_userrole_uniq_role_per_user"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
