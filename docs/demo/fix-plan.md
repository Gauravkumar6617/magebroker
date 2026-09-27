# Magento 2.4.7 Upgrade Fix Plan

Generated from `magebroker scan sample-magento --target 2.4.7`

**Health score before fixes: 10 / 100**  
**Total findings: 6 (4 critical, 2 warning)**

---

## Step 1 - B1: Align magento/framework constraint to locked version

**File:** `sample-magento/app/code/Acme/Checkout/composer.json`  
**Label:** auto  

**Before:**
```json
"magento/framework": "^102.0"
```

**After:**
```json
"magento/framework": "^103.0"
```

> The composer.lock pins `magento/framework` at `103.0.6`. The module constraint `^102.0` does not satisfy this version. Aligning the constraint to `^103.0` resolves the conflict.

---

## Step 2 - B5: Widen PHP constraint to include PHP 8.2 and 8.3

**File:** `sample-magento/app/code/Acme/Inventory/composer.json`  
**Label:** auto  

**Before:**
```json
"php": "~8.1.0"
```

**After:**
```json
"php": "~8.2.0||~8.3.0"
```

> Magento 2.4.7 requires PHP 8.2 or 8.3. The current constraint `~8.1.0` is incompatible. Widening to `~8.2.0||~8.3.0` unblocks the upgrade.

---

## Step 3 - B2: Add missing acme/payment-gateway dependency

**File:** `sample-magento/app/code/Acme/Payment/composer.json`  
**Label:** manual  

**Before:**
```
(no change to file — package must be fetched from a remote repository)
```

**After:**
```
(no change to file — composer.lock must be updated by running the command below)
```

> `acme/payment-gateway ^1.0` is declared as a dependency of `Acme_Payment` but is absent from `composer.lock`. This cannot be resolved without network access to fetch and lock the package.  
> **Command the developer must run:**
> ```bash
> composer require acme/payment-gateway:'^1.0'
> ```

---

## Step 4 - B3: Remove circular sequence from Acme_Catalog

**File:** `sample-magento/app/code/Acme/Catalog/etc/module.xml`  
**Label:** auto  

**Before:**
```xml
        <sequence>
            <module name="Magento_Catalog"/>
            <module name="Magento_Store"/>
            <module name="Acme_Checkout"/><!-- B3: circular — Acme_Checkout also sequences Acme_Catalog -->
        </sequence>
```

**After:**
```xml
        <sequence>
            <module name="Magento_Catalog"/>
            <module name="Magento_Store"/>
        </sequence>
```

> `Acme_Checkout` already sequences `Acme_Catalog` (load Catalog before Checkout). Adding the reciprocal edge in `Acme_Catalog` creates a cycle. Removing `<module name="Acme_Checkout"/>` from `Acme_Catalog` breaks the cycle while preserving the intended load order.

---

## Step 5 - B4: Remove duplicate ProductRepositoryInterface preference from Acme_Customer

**File:** `sample-magento/app/code/Acme/Customer/etc/di.xml`  
**Label:** auto  

**Before:**
```xml
<?xml version="1.0"?>
<!--
    BUG B4: Both Acme_Customer and Acme_Catalog declare a <preference> for the same interface
            Magento\Catalog\Api\ProductRepositoryInterface (line 9 here; original in
            Acme_Catalog/etc/di.xml line 10)
-->
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="urn:magento:framework:ObjectManager/etc/config.xsd">
    <!-- B4: duplicate preference — same interface also preferred in Acme_Catalog/etc/di.xml -->
    <preference for="Magento\Catalog\Api\ProductRepositoryInterface"
                type="Acme\Customer\Model\ProductRepository"/>
    <preference for="Magento\Customer\Api\CustomerRepositoryInterface"
                type="Acme\Customer\Model\CustomerRepository"/>
</config>
```

**After:**
```xml
<?xml version="1.0"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="urn:magento:framework:ObjectManager/etc/config.xsd">
    <preference for="Magento\Customer\Api\CustomerRepositoryInterface"
                type="Acme\Customer\Model\CustomerRepository"/>
</config>
```

> `Acme_Catalog` is the authoritative module declaring the preference for `Magento\Catalog\Api\ProductRepositoryInterface`. The duplicate in `Acme_Customer` causes non-deterministic DI resolution. Only the `CustomerRepositoryInterface` preference (unique to `Acme_Customer`) is retained.

---

## Step 6 - B6: Remove ghost sequence entry Acme_Analytics from Acme_Search

**File:** `sample-magento/app/code/Acme/Search/etc/module.xml`  
**Label:** auto  

**Before:**
```xml
        <sequence>
            <module name="Magento_Search"/>
            <module name="Acme_Analytics"/><!-- B6: ghost — Acme_Analytics module does not exist -->
        </sequence>
```

**After:**
```xml
        <sequence>
            <module name="Magento_Search"/>
        </sequence>
```

> `Acme_Analytics` does not exist in `app/code` or `composer.lock`. Magento's sequence sorter will fatal on `setup:upgrade` if a sequenced module is absent. The entry must be removed.

---

## Summary Table

| Step | ID  | Type                  | Label  | File                                                              |
|------|-----|-----------------------|--------|-------------------------------------------------------------------|
| 1    | B1  | version_conflict      | auto   | sample-magento/app/code/Acme/Checkout/composer.json              |
| 2    | B5  | upgrade_blocker       | auto   | sample-magento/app/code/Acme/Inventory/composer.json             |
| 3    | B2  | missing_dep           | manual | sample-magento/app/code/Acme/Payment/composer.json               |
| 4    | B3  | circular_sequence     | auto   | sample-magento/app/code/Acme/Catalog/etc/module.xml              |
| 5    | B4  | duplicate_preference  | auto   | sample-magento/app/code/Acme/Customer/etc/di.xml                 |
| 6    | B6  | ghost_sequence        | auto   | sample-magento/app/code/Acme/Search/etc/module.xml               |
