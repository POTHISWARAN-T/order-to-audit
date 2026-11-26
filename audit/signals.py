from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_save

from .context import current_user
from .models import AuditLog

# The records whose history the auditor can ask for
TRACKED_MODELS = [
    "masters.Item",
    "masters.BOM",
    "masters.BOMLine",
    "masters.Customer",
    "masters.Supplier",
    "inventory.Purchase",
    "production.ProductionRun",
    "production.ProductionRunLine",
    "production.RunOverhead",
    "sales.Order",
    "sales.OrderLine",
    "billing.Invoice",
    "billing.InvoiceLine",
    "billing.CreditNote",
    "billing.Payment",
]


def field_values(instance):
    """Every stored field of a record as plain text, so before and after can be compared."""
    values = {}
    for field in instance._meta.concrete_fields:
        value = getattr(instance, field.attname)
        if value is not None and field.get_internal_type() == "DecimalField":
            value = f"{field.to_python(value):.{field.decimal_places}f}"
        values[field.attname] = str(value)
    return values


def acting_user_id():
    user = current_user.get()
    if user is not None and user.is_authenticated:
        return user.pk
    return None


def write_log(model, instance, action, changes):
    AuditLog.objects.create(
        model_name=model._meta.label,
        object_id=str(instance.pk),
        object_repr=str(instance)[:200],
        action=action,
        changes=changes,
        user_id=acting_user_id(),
    )


def remember_old_values(sender, instance, **kwargs):
    """Runs just before a save: keep what the record looked like before."""
    instance._audit_old = None
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        if old is not None:
            instance._audit_old = field_values(old)


def log_save(sender, instance, created, **kwargs):
    new = field_values(instance)
    old = getattr(instance, "_audit_old", None)
    if created or old is None:
        details = "; ".join(f"{name}={value}" for name, value in new.items())
        write_log(sender, instance, AuditLog.CREATED, details)
        return
    differences = [
        f"{name}: {old.get(name)} -> {value}"
        for name, value in new.items()
        if old.get(name) != value
    ]
    if differences:
        write_log(sender, instance, AuditLog.CHANGED, "; ".join(differences))


def log_delete(sender, instance, **kwargs):
    write_log(sender, instance, AuditLog.DELETED, "")


def connect_all():
    for label in TRACKED_MODELS:
        model = apps.get_model(label)
        pre_save.connect(remember_old_values, sender=model, dispatch_uid=f"audit-pre-{label}")
        post_save.connect(log_save, sender=model, dispatch_uid=f"audit-save-{label}")
        post_delete.connect(log_delete, sender=model, dispatch_uid=f"audit-delete-{label}")