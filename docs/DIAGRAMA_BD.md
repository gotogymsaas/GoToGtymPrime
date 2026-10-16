# Diagrama de la base de datos

Diagramas entidad-relación (Mermaid) de GoToGym Prime, generados desde los modelos de Django con `python Temp/generar_diagrama_bd.py`. No editar a mano: volver a generar cuando cambien los modelos.

## De dónde sale y qué tan "real" es

- **Fuente:** los modelos y las 86 migraciones del repositorio (42 tablas, sin contar la tabla de caché `django_cache` que crea `migrate`). Es exactamente el esquema que `migrate` construye en PostgreSQL, incluidas las tablas intermedias de las relaciones muchos-a-muchos.
- **Contraste con producción (15-oct-2026):** en una restauración del respaldo de `psql-gotogym-prod` (punto en el tiempo del 15-oct, 20:51 hora de Colombia) la base `gotogym_prime` tenía **44 tablas y 80 migraciones aplicadas**, la última el 10-oct. Las diferencias conocidas con el código de aquel momento: `django_cache` (la crea `migrate`, no es un modelo), dos tablas que no se identificaron (probablemente restos de la base "influencer" original que adapta una migración; no se consultaron sus nombres) y la migración `orders 0011` (columna `Order.language`, 15-oct), que pudo no estar aplicada en esa copia. Las migraciones posteriores (restricciones, índices, historial de estados) no están aplicadas en producción hasta el siguiente despliegue.
- **Límite:** este documento no se generó leyendo el catálogo de la base viva (el servidor de producción solo acepta conexiones desde Azure y no se abrió su firewall). Para confirmarlo columna por columna, ejecutar `python manage.py inspectdb` o `\d+` con `psql` desde el App Service.
- Notación: `PK` clave primaria, `FK` clave foránea, `UK` única. `||--o{` es uno a muchos obligatorio; `|o--o{`, uno a muchos con la clave foránea opcional (nula); `||--o|`, uno a uno. Los tipos son los de PostgreSQL abreviados (`varchar150` = `varchar(150)`, `numeric12_2` = `numeric(12,2)`).

## Vista general (solo relaciones)

```mermaid
erDiagram
    accounts_customeraddress
    accounts_user ||--o{ accounts_customeraddress : "user_id"
    accounts_customersegment
    accounts_user
    accounts_user_customer_segments
    accounts_user ||--o{ accounts_user_customer_segments : "user_id"
    accounts_customersegment ||--o{ accounts_user_customer_segments : "customersegment_id"
    accounts_user_groups
    accounts_user ||--o{ accounts_user_groups : "user_id"
    auth_group ||--o{ accounts_user_groups : "group_id"
    accounts_user_user_permissions
    accounts_user ||--o{ accounts_user_user_permissions : "user_id"
    auth_permission ||--o{ accounts_user_user_permissions : "permission_id"
    auth_group
    auth_group_permissions
    auth_group ||--o{ auth_group_permissions : "group_id"
    auth_permission ||--o{ auth_group_permissions : "permission_id"
    auth_permission
    django_content_type ||--o{ auth_permission : "content_type_id"
    django_content_type
    django_session
    django_admin_log
    accounts_user ||--o{ django_admin_log : "user_id"
    django_content_type |o--o{ django_admin_log : "content_type_id"
    products_brand
    products_product
    products_productcategory ||--o{ products_product : "category_id"
    products_brand |o--o{ products_product : "brand_id"
    products_product_tags
    products_product ||--o{ products_product_tags : "product_id"
    products_producttag ||--o{ products_product_tags : "producttag_id"
    products_productcategory
    products_productmedia
    products_product ||--o{ products_productmedia : "product_id"
    products_productvariant |o--o{ products_productmedia : "variant_id"
    products_productreview
    products_product ||--o{ products_productreview : "product_id"
    orders_orderitem ||--o| products_productreview : "order_item_id"
    accounts_user ||--o{ products_productreview : "user_id"
    products_producttag
    products_productvariant
    products_product ||--o{ products_productvariant : "product_id"
    inventory_inventory
    products_productvariant ||--o| inventory_inventory : "variant_id"
    inventory_inventoryadjustment
    inventory_inventory ||--o{ inventory_inventoryadjustment : "inventory_id"
    accounts_user |o--o{ inventory_inventoryadjustment : "created_by_id"
    orders_address
    orders_order ||--o| orders_address : "order_id"
    orders_coupon
    afiliados_perfilafiliado |o--o{ orders_coupon : "afiliado_id"
    accounts_customersegment |o--o{ orders_coupon : "customer_segment_id"
    orders_order
    accounts_user |o--o{ orders_order : "user_id"
    afiliados_perfilafiliado |o--o{ orders_order : "referred_by_id"
    orders_coupon |o--o{ orders_order : "coupon_id"
    orders_orderitem
    orders_order ||--o{ orders_orderitem : "order_id"
    products_productvariant |o--o{ orders_orderitem : "variant_id"
    orders_orderstatushistory
    orders_order ||--o{ orders_orderstatushistory : "order_id"
    accounts_user |o--o{ orders_orderstatushistory : "changed_by_id"
    payments_paymenttransaction
    orders_order ||--o{ payments_paymenttransaction : "order_id"
    payments_refund
    payments_paymenttransaction ||--o{ payments_refund : "payment_transaction_id"
    accounts_user |o--o{ payments_refund : "requested_by_id"
    shipping_shippingquote
    orders_order ||--o| shipping_shippingquote : "order_id"
    afiliados_commission
    afiliados_perfilafiliado ||--o{ afiliados_commission : "afiliado_id"
    orders_order ||--o| afiliados_commission : "order_id"
    accounts_user |o--o{ afiliados_commission : "adjusted_by_id"
    afiliados_withdrawalrequest |o--o{ afiliados_commission : "withdrawal_request_id"
    afiliados_withdrawalrequest |o--o{ afiliados_commission : "recovered_in_id"
    afiliados_configuracionprogramaafiliados
    afiliados_payoutaccount
    afiliados_perfilafiliado ||--o| afiliados_payoutaccount : "afiliado_id"
    afiliados_perfilafiliado
    accounts_user ||--o| afiliados_perfilafiliado : "user_id"
    accounts_user |o--o{ afiliados_perfilafiliado : "reviewed_by_id"
    afiliados_recursomarca
    afiliados_referralclick
    afiliados_perfilafiliado ||--o{ afiliados_referralclick : "afiliado_id"
    afiliados_socialnetwork
    afiliados_perfilafiliado ||--o{ afiliados_socialnetwork : "afiliado_id"
    afiliados_withdrawalrequest
    afiliados_perfilafiliado ||--o{ afiliados_withdrawalrequest : "afiliado_id"
    accounts_user |o--o{ afiliados_withdrawalrequest : "resolved_by_id"
    blog_category
    blog_post
    accounts_user ||--o{ blog_post : "author_id"
    blog_category |o--o{ blog_post : "category_id"
    analitica_eventoanalitica
    administracion_panelsettings
```

## Cuentas y acceso

Aplicaciones: `accounts`, `auth`, `contenttypes`, `sessions`, `admin`.

```mermaid
erDiagram
    accounts_customeraddress {
        bigint id PK
        bigint user_id FK
        varchar60 label
        varchar200 full_name
        varchar40 phone
        varchar80 country
        varchar80 department
        varchar80 city
        varchar20 postal_code
        varchar255 address_line
        varchar255 address_complement
        text notes
        bool is_default
        timestamptz created_at
    }
    accounts_customersegment {
        bigint id PK
        varchar80 name UK
        varchar255 description
    }
    accounts_user {
        bigint id PK
        varchar128 password
        timestamptz last_login
        bool is_superuser
        varchar150 username UK
        bool is_staff
        bool is_active
        timestamptz date_joined
        varchar254 email UK
        varchar150 first_name
        varchar150 last_name
        int age
        varchar40 phone
        bool accepted_terms
        timestamptz terms_accepted_at
        varchar128 terms_hash
        bool show_afiliado_modal
        bool es_afiliado
    }
    accounts_user_customer_segments {
        bigint id PK
        bigint user_id FK
        bigint customersegment_id FK
    }
    accounts_user_groups {
        bigint id PK
        bigint user_id FK
        int group_id FK
    }
    accounts_user_user_permissions {
        bigint id PK
        bigint user_id FK
        int permission_id FK
    }
    auth_group {
        int id PK
        varchar150 name UK
    }
    auth_group_permissions {
        int id PK
        int group_id FK
        int permission_id FK
    }
    auth_permission {
        int id PK
        varchar255 name
        int content_type_id FK
        varchar100 codename
    }
    django_content_type {
        int id PK
        varchar100 app_label
        varchar100 model
    }
    django_session {
        varchar40 session_key PK
        text session_data
        timestamptz expire_date
    }
    django_admin_log {
        int id PK
        timestamptz action_time
        bigint user_id FK
        int content_type_id FK
        text object_id
        varchar200 object_repr
        smallint action_flag
        text change_message
    }
    accounts_user ||--o{ accounts_customeraddress : "user_id"
    accounts_user ||--o{ accounts_user_customer_segments : "user_id"
    accounts_customersegment ||--o{ accounts_user_customer_segments : "customersegment_id"
    accounts_user ||--o{ accounts_user_groups : "user_id"
    auth_group ||--o{ accounts_user_groups : "group_id"
    accounts_user ||--o{ accounts_user_user_permissions : "user_id"
    auth_permission ||--o{ accounts_user_user_permissions : "permission_id"
    auth_group ||--o{ auth_group_permissions : "group_id"
    auth_permission ||--o{ auth_group_permissions : "permission_id"
    django_content_type ||--o{ auth_permission : "content_type_id"
    accounts_user ||--o{ django_admin_log : "user_id"
    django_content_type |o--o{ django_admin_log : "content_type_id"
```

## Catálogo e inventario

Aplicaciones: `products`, `inventory`.

```mermaid
erDiagram
    products_brand {
        bigint id PK
        varchar100 name UK
    }
    products_product {
        bigint id PK
        varchar150 name
        bigint category_id FK
        bigint brand_id FK
        text description
        numeric12_4 base_price
        int discount
        int stock
        bool featured
        varchar100 image
    }
    products_product_tags {
        bigint id PK
        bigint product_id FK
        bigint producttag_id FK
    }
    products_productcategory {
        bigint id PK
        varchar100 name UK
        text description
    }
    products_productmedia {
        bigint id PK
        bigint product_id FK
        bigint variant_id FK
        varchar100 image
        varchar200 alt_text
        int sort_order
        bool is_primary
    }
    products_productreview {
        bigint id PK
        bigint product_id FK
        bigint order_item_id FK,UK
        bigint user_id FK
        smallint rating
        text comment
        timestamptz created_at
        timestamptz updated_at
    }
    products_producttag {
        bigint id PK
        varchar40 name UK
        varchar50 slug UK
        varchar20 color_token
        bool is_active
    }
    products_productvariant {
        bigint id PK
        bigint product_id FK
        varchar64 sku UK
        varchar20 size
        varchar60 color
        numeric12_4 price_override
        numeric12_4 discount_price
        bool is_active
        timestamptz created_at
    }
    inventory_inventory {
        bigint id PK
        bigint variant_id FK,UK
        int quantity_available
        int quantity_reserved
        timestamptz updated_at
    }
    inventory_inventoryadjustment {
        bigint id PK
        bigint inventory_id FK
        int delta
        int quantity_after
        varchar20 reason
        bigint created_by_id FK
        timestamptz created_at
    }
    accounts_user {
        bigint id PK
    }
    orders_orderitem {
        bigint id PK
    }
    products_productcategory ||--o{ products_product : "category_id"
    products_brand |o--o{ products_product : "brand_id"
    products_product ||--o{ products_product_tags : "product_id"
    products_producttag ||--o{ products_product_tags : "producttag_id"
    products_product ||--o{ products_productmedia : "product_id"
    products_productvariant |o--o{ products_productmedia : "variant_id"
    products_product ||--o{ products_productreview : "product_id"
    orders_orderitem ||--o| products_productreview : "order_item_id"
    accounts_user ||--o{ products_productreview : "user_id"
    products_product ||--o{ products_productvariant : "product_id"
    products_productvariant ||--o| inventory_inventory : "variant_id"
    inventory_inventory ||--o{ inventory_inventoryadjustment : "inventory_id"
    accounts_user |o--o{ inventory_inventoryadjustment : "created_by_id"
```

## Pedidos, pagos y envíos

Aplicaciones: `orders`, `payments`, `shipping`.

```mermaid
erDiagram
    orders_address {
        bigint id PK
        bigint order_id FK,UK
        varchar200 full_name
        varchar40 phone
        varchar80 country
        varchar80 department
        varchar80 city
        varchar20 postal_code
        varchar255 address_line
        varchar255 address_complement
        text notes
    }
    orders_coupon {
        bigint id PK
        varchar30 code UK
        varchar12 discount_type
        numeric12_2 value
        numeric12_2 min_purchase
        timestamptz starts_at
        timestamptz ends_at
        int max_uses
        int times_used
        bool is_active
        bigint afiliado_id FK
        bigint customer_segment_id FK
        timestamptz created_at
        timestamptz updated_at
    }
    orders_order {
        bigint id PK
        bigint user_id FK
        varchar32 order_number UK
        varchar254 email
        varchar40 phone
        varchar3 currency
        numeric12_2 subtotal
        numeric12_2 shipping_cost
        numeric12_2 discount_total
        numeric12_2 total
        varchar20 order_status
        varchar20 payment_status
        text internal_note
        varchar8 language
        bigint referred_by_id FK
        bigint coupon_id FK
        timestamptz delivered_at
        timestamptz paid_at
        timestamptz shipped_at
        timestamptz cancelled_at
        varchar3 customer_document_type
        varchar20 customer_document_number
        timestamptz created_at
        timestamptz updated_at
    }
    orders_orderitem {
        bigint id PK
        bigint order_id FK
        bigint variant_id FK
        varchar150 product_name_snapshot
        varchar64 sku_snapshot
        varchar20 size_snapshot
        varchar60 color_snapshot
        numeric12_2 unit_price_snapshot
        int quantity
        numeric12_2 line_total
    }
    orders_orderstatushistory {
        bigint id PK
        bigint order_id FK
        varchar20 from_status
        varchar20 to_status
        bigint changed_by_id FK
        varchar255 note
        timestamptz created_at
    }
    payments_paymenttransaction {
        bigint id PK
        bigint order_id FK
        varchar30 provider
        varchar100 preference_id
        varchar100 payment_id
        varchar64 external_reference
        varchar20 status
        numeric12_2 amount
        varchar3 currency
        varchar64 idempotency_key UK
        jsonb raw_payload
        timestamptz created_at
        timestamptz updated_at
    }
    payments_refund {
        bigint id PK
        bigint payment_transaction_id FK
        numeric12_2 amount
        varchar12 status
        varchar100 provider_refund_id
        bigint requested_by_id FK
        text error_message
        timestamptz created_at
    }
    shipping_shippingquote {
        bigint id PK
        bigint order_id FK,UK
        varchar80 carrier_name
        varchar80 method_name
        numeric12_2 cost
        int estimated_days
        varchar64 tracking_code
        varchar20 shipping_status
    }
    accounts_customersegment {
        bigint id PK
    }
    accounts_user {
        bigint id PK
    }
    afiliados_perfilafiliado {
        bigint id PK
    }
    products_productvariant {
        bigint id PK
    }
    orders_order ||--o| orders_address : "order_id"
    afiliados_perfilafiliado |o--o{ orders_coupon : "afiliado_id"
    accounts_customersegment |o--o{ orders_coupon : "customer_segment_id"
    accounts_user |o--o{ orders_order : "user_id"
    afiliados_perfilafiliado |o--o{ orders_order : "referred_by_id"
    orders_coupon |o--o{ orders_order : "coupon_id"
    orders_order ||--o{ orders_orderitem : "order_id"
    products_productvariant |o--o{ orders_orderitem : "variant_id"
    orders_order ||--o{ orders_orderstatushistory : "order_id"
    accounts_user |o--o{ orders_orderstatushistory : "changed_by_id"
    orders_order ||--o{ payments_paymenttransaction : "order_id"
    payments_paymenttransaction ||--o{ payments_refund : "payment_transaction_id"
    accounts_user |o--o{ payments_refund : "requested_by_id"
    orders_order ||--o| shipping_shippingquote : "order_id"
```

## Programa de afiliados

Aplicaciones: `afiliados`.

```mermaid
erDiagram
    afiliados_commission {
        bigint id PK
        bigint afiliado_id FK
        bigint order_id FK,UK
        numeric12_2 amount
        numeric12_2 base_amount
        numeric5_2 rate_applied
        varchar12 status
        bool needs_review
        varchar255 review_reason
        timestamptz validation_ends_at
        timestamptz extended_until
        varchar255 extension_reason
        varchar255 adjustment_reason
        bigint adjusted_by_id FK
        timestamptz adjusted_at
        bigint withdrawal_request_id FK
        bigint recovered_in_id FK
        timestamptz created_at
        timestamptz updated_at
    }
    afiliados_configuracionprogramaafiliados {
        bigint id PK
        numeric5_2 default_commission_rate
        numeric5_2 default_customer_discount
        numeric12_2 minimum_payout
        int inactivity_days
        timestamptz updated_at
    }
    afiliados_payoutaccount {
        bigint id PK
        bigint afiliado_id FK,UK
        varchar150 first_name
        varchar150 last_name
        varchar40 phone
        varchar255 address
        varchar3 document_type
        varchar20 document_number
        varchar80 breb_key
        timestamptz terms_accepted_at
        timestamptz data_consent_at
        timestamptz created_at
        timestamptz updated_at
    }
    afiliados_perfilafiliado {
        bigint id PK
        bigint user_id FK,UK
        varchar36 referral_code UK
        numeric5_2 commission_rate
        numeric12_2 commission_balance
        int total_referred
        numeric12_2 total_sales
        timestamptz created_at
        bool is_active
        varchar12 status
        timestamptz reviewed_at
        bigint reviewed_by_id FK
        timestamptz terms_accepted_at
        varchar20 terms_version
        varchar150 first_name
        varchar150 last_name
        varchar40 phone
        varchar255 address
        varchar3 document_type
        varchar20 document_number
        text review_notes
        varchar500 rejection_reason
        timestamptz exit_requested_at
        timestamptz exit_effective_at
        timestamptz exited_at
        varchar12 exit_reason
        text exit_notes
    }
    afiliados_recursomarca {
        bigint id PK
        varchar120 title
        varchar300 description
        varchar100 file
        int order
        bool is_active
        timestamptz created_at
    }
    afiliados_referralclick {
        bigint id PK
        bigint afiliado_id FK
        timestamptz created_at
    }
    afiliados_socialnetwork {
        bigint id PK
        bigint afiliado_id FK
        varchar12 platform
        varchar60 other_name
        varchar60 username
        int followers
        timestamptz created_at
    }
    afiliados_withdrawalrequest {
        bigint id PK
        bigint afiliado_id FK
        numeric12_2 amount
        numeric12_2 recovery_amount
        numeric12_2 transaction_fee
        varchar12 status
        text payment_details
        timestamptz requested_at
        timestamptz resolved_at
        bigint resolved_by_id FK
    }
    accounts_user {
        bigint id PK
    }
    orders_order {
        bigint id PK
    }
    afiliados_perfilafiliado ||--o{ afiliados_commission : "afiliado_id"
    orders_order ||--o| afiliados_commission : "order_id"
    accounts_user |o--o{ afiliados_commission : "adjusted_by_id"
    afiliados_withdrawalrequest |o--o{ afiliados_commission : "withdrawal_request_id"
    afiliados_withdrawalrequest |o--o{ afiliados_commission : "recovered_in_id"
    afiliados_perfilafiliado ||--o| afiliados_payoutaccount : "afiliado_id"
    accounts_user ||--o| afiliados_perfilafiliado : "user_id"
    accounts_user |o--o{ afiliados_perfilafiliado : "reviewed_by_id"
    afiliados_perfilafiliado ||--o{ afiliados_referralclick : "afiliado_id"
    afiliados_perfilafiliado ||--o{ afiliados_socialnetwork : "afiliado_id"
    afiliados_perfilafiliado ||--o{ afiliados_withdrawalrequest : "afiliado_id"
    accounts_user |o--o{ afiliados_withdrawalrequest : "resolved_by_id"
```

## Contenido, analítica y panel

Aplicaciones: `blog`, `analitica`, `administracion`.

```mermaid
erDiagram
    blog_category {
        bigint id PK
        varchar100 name UK
        varchar120 slug UK
    }
    blog_post {
        bigint id PK
        varchar200 title
        varchar220 slug UK
        bigint author_id FK
        bigint category_id FK
        text excerpt
        text content
        text references
        varchar100 featured
        timestamptz published
        timestamptz updated
        int reading_time
        bool is_published
    }
    analitica_eventoanalitica {
        bigint id PK
        varchar64 nombre
        varchar300 ruta
        varchar64 sesion
        bool autenticado
        jsonb propiedades
        timestamptz creado
    }
    administracion_panelsettings {
        bigint id PK
        int low_stock_threshold
        int monthly_sales_goal
        timestamptz updated_at
    }
    accounts_user {
        bigint id PK
    }
    accounts_user ||--o{ blog_post : "author_id"
    blog_category |o--o{ blog_post : "category_id"
```

## Inventario de tablas

| Tabla | Modelo | Columnas | Relaciones salientes |
|---|---|---|---|
| `accounts_customeraddress` | accounts.CustomerAddress | 14 | accounts_user |
| `accounts_customersegment` | accounts.CustomerSegment | 3 | — |
| `accounts_user` | accounts.User | 18 | — |
| `accounts_user_customer_segments` | accounts.User_customer_segments | 3 | accounts_customersegment, accounts_user |
| `accounts_user_groups` | accounts.User_groups | 3 | accounts_user, auth_group |
| `accounts_user_user_permissions` | accounts.User_user_permissions | 3 | accounts_user, auth_permission |
| `auth_group` | auth.Group | 2 | — |
| `auth_group_permissions` | auth.Group_permissions | 3 | auth_group, auth_permission |
| `auth_permission` | auth.Permission | 4 | django_content_type |
| `django_content_type` | contenttypes.ContentType | 3 | — |
| `django_session` | sessions.Session | 3 | — |
| `django_admin_log` | admin.LogEntry | 8 | accounts_user, django_content_type |
| `products_brand` | products.Brand | 2 | — |
| `products_product` | products.Product | 10 | products_brand, products_productcategory |
| `products_product_tags` | products.Product_tags | 3 | products_product, products_producttag |
| `products_productcategory` | products.ProductCategory | 3 | — |
| `products_productmedia` | products.ProductMedia | 7 | products_product, products_productvariant |
| `products_productreview` | products.ProductReview | 8 | accounts_user, orders_orderitem, products_product |
| `products_producttag` | products.ProductTag | 5 | — |
| `products_productvariant` | products.ProductVariant | 9 | products_product |
| `inventory_inventory` | inventory.Inventory | 5 | products_productvariant |
| `inventory_inventoryadjustment` | inventory.InventoryAdjustment | 7 | accounts_user, inventory_inventory |
| `orders_address` | orders.Address | 11 | orders_order |
| `orders_coupon` | orders.Coupon | 14 | accounts_customersegment, afiliados_perfilafiliado |
| `orders_order` | orders.Order | 24 | accounts_user, afiliados_perfilafiliado, orders_coupon |
| `orders_orderitem` | orders.OrderItem | 10 | orders_order, products_productvariant |
| `orders_orderstatushistory` | orders.OrderStatusHistory | 7 | accounts_user, orders_order |
| `payments_paymenttransaction` | payments.PaymentTransaction | 13 | orders_order |
| `payments_refund` | payments.Refund | 8 | accounts_user, payments_paymenttransaction |
| `shipping_shippingquote` | shipping.ShippingQuote | 8 | orders_order |
| `afiliados_commission` | afiliados.Commission | 19 | accounts_user, afiliados_perfilafiliado, afiliados_withdrawalrequest, orders_order |
| `afiliados_configuracionprogramaafiliados` | afiliados.ConfiguracionProgramaAfiliados | 6 | — |
| `afiliados_payoutaccount` | afiliados.PayoutAccount | 13 | afiliados_perfilafiliado |
| `afiliados_perfilafiliado` | afiliados.PerfilAfiliado | 27 | accounts_user |
| `afiliados_recursomarca` | afiliados.RecursoMarca | 7 | — |
| `afiliados_referralclick` | afiliados.ReferralClick | 3 | afiliados_perfilafiliado |
| `afiliados_socialnetwork` | afiliados.SocialNetwork | 7 | afiliados_perfilafiliado |
| `afiliados_withdrawalrequest` | afiliados.WithdrawalRequest | 10 | accounts_user, afiliados_perfilafiliado |
| `blog_category` | blog.Category | 3 | — |
| `blog_post` | blog.Post | 13 | accounts_user, blog_category |
| `analitica_eventoanalitica` | analitica.EventoAnalitica | 7 | — |
| `administracion_panelsettings` | administracion.PanelSettings | 4 | — |
