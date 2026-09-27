# Sample Magento Project — Planted Bugs

This directory is the test fixture for MageBroker.
Six bugs are deliberately embedded so each analyzer detector has a concrete case to find.

---

## B1 — Version Conflict

**Type:** `version_conflict`  
**Severity:** critical

Two Acme modules require incompatible ranges of `magento/framework`.
The root `composer.lock` pins the package at `103.0.6`.

| File | Line | Constraint |
|------|------|------------|
| `app/code/Acme/Catalog/composer.json` | 7 | `"magento/framework": "^103.0"` ✅ matches lock |
| `app/code/Acme/Checkout/composer.json` | 7 | `"magento/framework": "^102.0"` ❌ does NOT match `103.0.6` |

`^102.0` means `>=102.0.0, <103.0.0` — the locked version `103.0.6` falls outside this range.

**Fix:** Update `Acme_Checkout/composer.json` line 7: `"magento/framework": "^103.0"`.

---

## B2 — Missing Dependency

**Type:** `missing_dep`  
**Severity:** critical

`Acme_Payment` requires a Composer package that is not present in `composer.lock`.

| File | Line | Missing package |
|------|------|-----------------|
| `app/code/Acme/Payment/composer.json` | 8 | `"acme/payment-gateway": "^1.0"` |

`composer.lock` contains no entry for `acme/payment-gateway`.

**Fix (manual):** Run `composer require acme/payment-gateway:^1.0` and commit the updated lock file.

---

## B3 — Circular Sequence

**Type:** `circular_sequence`  
**Severity:** critical

`Acme_Catalog` and `Acme_Checkout` each declare the other in their `<sequence>`, forming a cycle.

| File | Line | Sequence entry |
|------|------|----------------|
| `app/code/Acme/Catalog/etc/module.xml` | 11 | `<module name="Acme_Checkout"/>` |
| `app/code/Acme/Checkout/etc/module.xml` | 13 | `<module name="Acme_Catalog"/>` |

Magento's module loader cannot determine load order when two modules depend on each other.

**Fix:** Remove the `<module name="Acme_Catalog"/>` entry from `Acme_Checkout/etc/module.xml` line 13.

---

## B4 — Duplicate DI Preference

**Type:** `duplicate_preference`  
**Severity:** warning

Two modules both declare a `<preference>` for `Magento\Catalog\Api\ProductRepositoryInterface`.
The last module loaded wins, making the effective implementation unpredictable.

| File | Line | Preference type |
|------|------|-----------------|
| `app/code/Acme/Catalog/etc/di.xml` | 10 | `Acme\Catalog\Model\ProductRepository` |
| `app/code/Acme/Customer/etc/di.xml` | 10 | `Acme\Customer\Model\ProductRepository` |

**Fix:** Remove the `<preference>` block at line 10 from `Acme_Customer/etc/di.xml`.

---

## B5 — Upgrade Blocker (PHP constraint)

**Type:** `upgrade_blocker`  
**Severity:** critical

`Acme_Inventory` pins PHP to `~8.1.0` (only `8.1.x`).
Magento 2.4.7 requires PHP `8.2` or `8.3` — this module cannot be loaded on 2.4.7.

| File | Line | Constraint |
|------|------|------------|
| `app/code/Acme/Inventory/composer.json` | 6 | `"php": "~8.1.0"` |

`data/compat.json` records: `2.4.7 → PHP ["8.2", "8.3"]`.

**Fix:** Update `Acme_Inventory/composer.json` line 6: `"php": "~8.2.0 || ~8.3.0"`.

---

## B6 — Ghost Sequence (module not present)

**Type:** `ghost_sequence`  
**Severity:** warning

`Acme_Search` sequences `Acme_Analytics`, but no such module exists in `app/code/Acme/` and no
Composer package provides it.

| File | Line | Ghost module |
|------|------|--------------|
| `app/code/Acme/Search/etc/module.xml` | 11 | `<module name="Acme_Analytics"/>` |

Magento silently skips missing sequence modules in development but may fail in strict mode or
during `setup:upgrade`.

**Fix:** Remove the `<module name="Acme_Analytics"/>` entry from `Acme_Search/etc/module.xml` line 11.
