"""English version of the policy pages (courtesy translation).

Same structure as `politicas_contenido` (the Spanish text is the original and
prevails in case of discrepancy). Legal periods come from Law 1480 of 2011,
Decree 587 of 2016 and Law 1581 of 2012; the brand's own periods (exchanges,
warranty) are commercial decisions and are changed in the Spanish module and
here at the same time.
"""
from .politicas_contenido import CORREO_PRIVACIDAD, CORREO_SOPORTE, RESPONSABLE

ACTUALIZADO = 'Last updated: October 2026.'

PRIVACIDAD = {
    'title': 'Privacy policy',
    'summary': 'We protect your data and process it under principles of security, transparency and control by the data subject.',
    'sections': [
        {'title': 'What you should know', 'paragraphs': [
            'GoToGym processes the information needed to manage your account, your purchases, '
            'customer service and the communications you have authorized.',
            'We do not sell your data. You can request access, correction, update or '
            f'deletion by writing to {CORREO_PRIVACIDAD}.',
        ]},
        {'title': 'More information', 'paragraphs': [
            'What data we collect, what we use it for, who we share it with and how to '
            'exercise your rights is detailed in the personal data processing policy.',
        ]},
    ],
}

CAMBIOS = {
    'title': 'Exchanges',
    'summary': 'How to request a size or color exchange and what condition the garment must be in.',
    'sections': [
        {'title': 'When you can ask for an exchange', 'paragraphs': [
            'You can request a size or color exchange within 15 calendar days after your order is delivered.',
            'Exchanges are subject to the availability of the size or color you want. If we do not '
            'have it in stock, we offer you another option or a refund.',
        ]},
        {'title': 'Condition of the garment', 'paragraphs': [
            'The garment must be unused, unwashed, free of odors and alterations, with its original '
            'tags and in its packaging.',
        ]},
        {'title': 'How to do it', 'paragraphs': [
            f'Write to us at {CORREO_SOPORTE} or through the contact section with your order number '
            '(GTG-YYYYMM-0000), the garment and the size or color you prefer. We will confirm how to '
            'send it and tell you the shipping cost before arranging the exchange.',
            'If the exchange is due to a mistake on our part or a defect in the garment, it costs you nothing.',
        ]},
        {'title': 'Exchange and right of withdrawal', 'paragraphs': [
            'The exchange is an additional benefit from GoToGym and does not replace your legal rights: '
            'if you would rather return your purchase, see the returns policy.',
        ]},
    ],
}

DEVOLUCIONES = {
    'title': 'Returns',
    'summary': 'How to exercise your right of withdrawal or return a product that is defective or different from what you bought.',
    'sections': [
        {'title': 'Right of withdrawal', 'paragraphs': [
            'Since you buy at a distance, you can change your mind and return your purchase without giving a reason '
            'within 5 business days after your order is delivered (article 47 of Law 1480 of 2011).',
            'The garment must arrive in the same condition in which you received it: unused, unwashed, with its '
            'tags and in its packaging. Return shipping costs are borne by you.',
            'You must let us know within that period by writing to '
            f'{CORREO_SOPORTE} with your order number.',
        ]},
        {'title': 'Defective product or different from your order', 'paragraphs': [
            'If your order arrives with a manufacturing defect, damaged, or not matching what you bought, '
            'let us know as soon as possible with your order number and photographs of the garment and its packaging. '
            'In these cases you do not pay for return shipping.',
            'Manufacturing defects are handled under the warranty; see the warranty policy.',
        ]},
        {'title': 'Refund', 'paragraphs': [
            'Once we receive the garment and check its condition, we refund the money through the same payment '
            'method you used, without deductions or withholdings, and no later than 30 calendar days '
            'after the date you exercised your right. How long the money takes to appear in your '
            'account depends on your bank or payment method.',
        ]},
        {'title': 'Payment reversal', 'paragraphs': [
            'If you paid by card or another electronic instrument and were a victim of fraud, did not request '
            'the purchase, did not receive the product, or received a different or defective one, you can ask for '
            'a payment reversal (article 51 of Law 1480 of 2011 and Decree 587 of 2016). You must file '
            'the complaint with us and notify the issuer of your payment instrument within '
            '5 business days after you learned of the transaction.',
        ]},
    ],
}

GARANTIA = {
    'title': 'Warranty',
    'summary': 'The coverage available for possible manufacturing defects.',
    'sections': [
        {'title': 'What it covers', 'paragraphs': [
            'GoToGym garments carry a warranty against manufacturing defects for 3 months after delivery, '
            'under normal conditions of use and care. It is a warranty of quality, suitability '
            'and proper functioning in accordance with Law 1480 of 2011.',
        ]},
        {'title': 'What it does not cover', 'paragraphs': [
            'It does not cover normal wear and tear, damage from misuse, washing or ironing other than as '
            'indicated on the label, cuts, burns, stains, or alterations or repairs made by '
            'third parties.',
        ]},
        {'title': 'How to claim it', 'paragraphs': [
            f'Write to us at {CORREO_SOPORTE} with your order number, photographs of the defect and a '
            'short description. We review your case and tell you how to send the garment, at no '
            'shipping cost to you when the warranty applies.',
        ]},
        {'title': 'What remedy you get', 'paragraphs': [
            'If the warranty applies, we repair or replace the garment with an identical or equivalent one. '
            'If the defect cannot be fixed or appears again, you can choose between a new replacement '
            'or a refund of the amount paid.',
            'This warranty does not limit the rights that Colombian law grants you as a consumer. '
            'If you disagree with our response, you can turn to the Superintendence of '
            'Industry and Commerce.',
        ]},
    ],
}

ENVIOS = {
    'title': 'Shipping',
    'summary': 'How the time and cost of getting your order to you are calculated.',
    'sections': [
        {'title': 'Coverage and cost', 'paragraphs': [
            'We ship throughout Colombia. The cost depends on the delivery city: there is one '
            'flat rate for Bogotá, Medellín, Cali, Barranquilla and Bucaramanga, and another for the rest '
            'of the country. You always see it calculated at checkout, before paying, and it is added to the order total.',
        ]},
        {'title': 'Delivery times', 'paragraphs': [
            'Once payment is confirmed we prepare your order. The estimated delivery time is about '
            '3 business days in major cities and about 6 business days in the rest of the country, counted '
            'from payment confirmation. These are estimates: they may vary due to the carrier, the weather '
            'or conditions in the area.',
            'We email you when your order ships and you can check its status under '
            '"My orders" in your account.',
        ]},
        {'title': 'Address and receipt', 'paragraphs': [
            'Check that the address, city and phone number are complete: a wrong address or '
            'an absent recipient may delay delivery or cause re-shipping costs.',
            'When you receive the package, check that the packaging is in good condition. If you notice damage or a '
            f'difference from your order, write to us as soon as possible at {CORREO_SOPORTE}.',
        ]},
    ],
}

PAGOS = {
    'title': 'Payments',
    'summary': 'How we protect the payment process and what information we never store.',
    'sections': [
        {'title': 'How you pay', 'paragraphs': [
            'Payments are processed through Mercado Pago. When you confirm your order we take you to its '
            'secure platform, where you choose among the payment methods it has enabled (for example '
            'credit and debit cards, PSE or cash payment, depending on availability). All prices '
            'are in Colombian pesos (COP).',
        ]},
        {'title': 'Security', 'paragraphs': [
            'GoToGym does not request, see or store your card details or your banking passwords: they are '
            'entered only on Mercado Pago. We only receive the payment status '
            '(approved, pending or rejected).',
        ]},
        {'title': 'Confirmation and pending payments', 'paragraphs': [
            'Your order is confirmed when the payment is approved. Until then it stays "pending payment" '
            'and units are not reserved: if someone else buys the last unit before your payment is '
            'approved, we let you know and refund your money.',
            'If the payment is not completed within 48 hours after the order is created, '
            'it is cancelled automatically. You can place your order again whenever you like.',
        ]},
        {'title': 'Rejected payments and refunds', 'paragraphs': [
            'If your payment is rejected you can try again with another method. Refunds are made '
            'through the same payment method used; see the returns policy for the time limits.',
            f'For any charge you do not recognize or any question about a payment, write to us at {CORREO_SOPORTE}.',
        ]},
        {'title': 'Who sells to you', 'paragraphs': [
            f'The garments on gotogym.store are sold by {RESPONSABLE}, a company based in Bogotá D.C., '
            f'Colombia, owner of the GoToGym brand. Help with your purchase: {CORREO_SOPORTE}.',
        ]},
    ],
}

TRATAMIENTO_DATOS = {
    'title': 'Personal data processing',
    'summary': 'The purposes and principles applied to the information you share with GoToGym.',
    'sections': [
        {'title': 'Data controller', 'paragraphs': [
            f'{RESPONSABLE}, which operates the GoToGym brand, based in Bogotá D.C., Colombia, is the '
            'controller of your personal data, in accordance with Law 1581 of 2012, '
            'Decree 1377 of 2013 (compiled in Decree 1074 of 2015) and the other rules that '
            f'complement them. Contact: {CORREO_PRIVACIDAD}.',
        ]},
        {'title': 'What data we collect', 'paragraphs': [
            'Identification and contact data (name, email, phone, age if you provide it), '
            'delivery data (address, city, department), data about your orders and payments (no card '
            'data), and site usage data that does not identify you, such as the pages visited.',
            'If you take part in the affiliate program, also the data needed to pay you '
            'commissions. We do not request sensitive data.',
        ]},
        {'title': 'What we use it for', 'paragraphs': [
            'Managing your account and orders, processing payments and shipments, handling requests, exchanges, '
            'warranties and returns, meeting legal and accounting obligations, improving the site and, '
            'only if you authorize it, sending you commercial communications.',
        ]},
        {'title': 'Who we share it with', 'paragraphs': [
            'With providers that help us operate and that process the data only for that purpose: the payment '
            'gateway, carriers, the email service and the infrastructure where '
            'the site is hosted, which may be outside Colombia. Also with authorities when the '
            'law requires it. We do not sell your data.',
        ]},
        {'title': 'Your rights', 'paragraphs': [
            'As a data subject you can access, update and correct your data; request proof of the authorization; '
            'be informed of how it is used; revoke the authorization and request deletion when '
            'legal principles and guarantees are not respected; access your data free of charge; and '
            'file complaints with the Superintendence of Industry and Commerce.',
        ]},
        {'title': 'How to exercise them', 'paragraphs': [
            f'Write to {CORREO_PRIVACIDAD} stating your name, your account email and what you request. '
            'We answer queries within a maximum of 10 business days and claims within a maximum of '
            '15 business days counted from the day after receipt; if we need more time, we '
            'tell you the reason and the new date, within the limits set by law.',
        ]},
        {'title': 'Security and retention', 'paragraphs': [
            'We apply technical and organizational measures to protect your data: encrypted connection, access '
            'control and securely stored passwords. We keep the data while you maintain '
            'a relationship with GoToGym and for the time required by legal obligations.',
            'We update this policy when our practices or the law change; the current version '
            f'is the one published here. {ACTUALIZADO}',
        ]},
    ],
}

COOKIES = {
    'title': 'Cookie policy',
    'summary': 'What GoToGym stores in your browser, what for, and how to change your decision whenever you want.',
    'sections': [
        {'title': 'What cookies are', 'paragraphs': [
            'Cookies are small files that a site stores in your browser to remember information '
            'between one visit and the next. At GoToGym we only use those the store needs to work and, if '
            'you accept, anonymous measurement of how the site is used.',
            'We do not use advertising or cross-site tracking cookies, we do not sell information about you, '
            'and the site does not load third-party scripts, fonts or images.',
        ]},
        {'title': 'What we store', 'paragraphs': [
            'This is the complete list of what the site stores in your browser.',
        ], 'table': {
            'headers': ['Name', 'What it is for', 'Type', 'Duration'],
            'rows': [
                ['sessionid',
                 'Keeps your session, your shopping cart and the affiliate code if you arrived through their link.',
                 'Necessary', '2 weeks'],
                ['csrftoken',
                 'Protects the site forms against forged submissions.',
                 'Necessary', 'Up to 1 year'],
                ['django_language',
                 'Remembers the language you chose. It is only created if you change it.',
                 'Necessary', 'Until the browser is closed'],
                ['gtg_cookies',
                 'Stores your choice about cookies so we do not ask you on every visit.',
                 'Necessary', '12 months'],
                ['ARRAffinity, ARRAffinitySameSite',
                 'Set by the hosting service (Azure App Service) to route your requests to the same server.',
                 'Necessary', 'Until the browser is closed'],
                ['gtg_atribucion',
                 'Browser session storage. Only if you accept analytics: remembers that we have already recorded where you came from in this visit.',
                 'Analytics', 'Until the tab is closed'],
            ],
        }},
        {'title': 'Anonymous measurement of site usage', 'paragraphs': [
            'Only if you accept it in the banner, we measure which pages are visited, which buttons are pressed, what is '
            'searched for, which products are viewed or added to the cart and how many orders are created. Each visit carries '
            'a random identifier unrelated to your name or your email, and we do not combine this data with '
            'your identity. We use it only to improve the store.',
            'If you do not accept it, or your browser sends the "Do Not Track" or Global Privacy Control signal, we do not measure '
            'anything. Accepting or rejecting analytics does not change in any way what you can buy or how.',
        ]},
        {'title': 'Third-party services', 'paragraphs': [
            'When you pay, we take you to Mercado Pago, which processes the payment and may store its own '
            'cookies on its platform, under its policy. Links to our social networks open their '
            'sites, which have their own policies.',
        ]},
        {'title': 'How to change your decision', 'paragraphs': [
            'You can change it whenever you want with the button below. '
            'You can also delete or block cookies from your browser settings; '
            'note that if you block the necessary ones, you will not be able to log in or use the cart.',
        ], 'accion_cookies': 'Open cookie preferences'},
        {'title': 'Contact and updates', 'paragraphs': [
            f'If you have questions about this policy, write to {CORREO_PRIVACIDAD}. We update this policy '
            f'when the cookies we use change; the current version is the one published here. {ACTUALIZADO}',
        ]},
    ],
}
