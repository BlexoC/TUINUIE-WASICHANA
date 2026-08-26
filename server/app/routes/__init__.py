"""Application route package.

Register blueprints here if importing this package directly.
"""

from .reminders import bp as reminders_bp
from .beneficiaries import beneficiaries_bp
from .inventory import inventory_bp
from .charity import charity_bp

__all__ = ["reminders_bp", "beneficiaries_bp", "inventory_bp", "charity_bp"]
