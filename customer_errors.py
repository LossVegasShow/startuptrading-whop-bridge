"""Customer-friendly error handling.

Browsers get a branded page (or, inside onboarding, an inline banner) with a
clear next step instead of raw JSON. API clients, webhooks, health checks and
operator routes keep the original JSON responses and status codes.
"""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

# Routes that must always keep machine-readable responses.
JSON_ONLY_PREFIXES = ('/webhooks', '/health', '/admin', '/static')

# (substring of the internal detail, key). First match wins, so specific
# phrases come before general ones.
DETAIL_KEYS = [
    ('Wait a minute', 'wait'),
    ('Too many codes requested today', 'code_cap'),
    ('Invalid or expired verification code', 'bad_code'),
    ('Valid NinjaTrader email required', 'bad_email'),
    ('Invalid onboarding path', 'bad_input'),
    ('linked to another account', 'nt_taken'),
    ('That NinjaTrader email is already linked', 'nt_taken'),
    ('NinjaTrader account already linked', 'nt_locked'),
    ('still active on another membership', 'nt_active_elsewhere'),
    ('license sync is in progress', 'busy'),
    ('support review', 'needs_support'),
    ('Account linking is not pending', 'not_pending'),
    ('Verification request does not match', 'not_pending'),
    ('Verify your Whop purchasing email first', 'buyer_first'),
    ('Membership email must be verified first', 'buyer_first'),
    ('Invalid form security token', 'stale'),
    ('Email delivery is temporarily unavailable', 'email_down'),
    ('Email service not configured', 'email_down'),
    ('Resend sender not configured', 'email_down'),
    ('No eligible StartUpTrading membership', 'no_membership'),
    ('Membership identity conflict', 'needs_support'),
    ('Use your private activation invitation', 'session'),
    ('Activation session has expired', 'session'),
    ('Invitation invalid or expired', 'invite'),
    ('Sign-in state expired', 'signin'),
    ('Whop sign-in declined or incomplete', 'signin'),
    ('nonce verification failed', 'signin'),
    ('Whop profile is missing required identity', 'signin'),
    ('Whop OAuth not configured', 'unavailable'),
    ('Whop membership could not be checked', 'whop_down'),
    ('Whop token', 'whop_down'),
    ('Whop profile lookup failed', 'whop_down'),
]

# key -> (title, explanation, primary action)
# Actions: 'onboarding' (back to the form), 'signin' (Whop sign-in again),
# 'subscribe' (checkout, if configured), 'support', 'home'.
MESSAGES = {
    'bad_code': ("That code didn't work",
                 "Codes expire after 10 minutes and allow five attempts. Use the newest email, or send a fresh code.",
                 'onboarding'),
    'code_cap': ('Too many codes today',
                 "For your security you can request up to 10 codes a day. Try again tomorrow, or contact support and we'll help.",
                 'support'),
    'wait': ('A code is already on its way',
             "You can request a new one 60 seconds after the last. Check your spam or promotions folder in the meantime.",
             'onboarding'),
    'bad_email': ("That email doesn't look right",
                  'Enter the email address you use to sign in to NinjaTrader.', 'onboarding'),
    'bad_input': ('Something was missing',
                  'Please fill in every field and try again.', 'onboarding'),
    'nt_taken': ('That NinjaTrader email is already linked',
                 "It's connected to a different StartUpTrading membership. Contact support and we'll sort it out.",
                 'support'),
    'nt_locked': ('Your NinjaTrader account is already connected',
                  "To switch to a different NinjaTrader account, contact support so your indicator licenses move safely.",
                  'support'),
    'nt_active_elsewhere': ('That NinjaTrader account is active on another membership',
                            "Your indicators are already licensed through your other StartUpTrading membership. "
                            "Contact support if you'd like to move them to this one.",
                            'support'),
    'busy': ('One moment',
             "We're finishing an update to your account. Wait a minute, then enter your code again.",
             'onboarding'),
    'needs_support': ('This one needs a quick look from our team',
                      "Your account needs a manual check before we can continue. Contact support and we'll fix it with you.",
                      'support'),
    'not_pending': ('Start verification again',
                    'Enter your NinjaTrader email to get a new code.', 'onboarding'),
    'buyer_first': ('Confirm your membership first',
                    'Verify your Whop purchase email in step 1, then continue.', 'onboarding'),
    'stale': ('This page was open for a while',
              'For your security, please try that again.', 'onboarding'),
    'email_down': ("We couldn't send the email",
                   'Our email service is having a moment. Try again in a few minutes. If it keeps happening, contact support.',
                   'onboarding'),
    'no_membership': ("We couldn't find an active membership on that Whop account",
                      'Sign in with the Whop account you used to subscribe. Different email from your purchase? '
                      "That's fine. It's the Whop account that matters.",
                      'signin'),
    'session': ('Your activation session ended',
                "Sign in with Whop again and you'll pick up right where you left off.", 'signin'),
    'invite': ('This invitation link has expired',
               'Invitation links work once and expire after 72 hours. Sign in with Whop instead, or ask support for a new link.',
               'signin'),
    'signin': ("Whop sign-in didn't finish",
               'That can happen if the window sat open too long or sign-in was cancelled. Try again.', 'signin'),
    'whop_down': ("We couldn't reach Whop",
                  "Whop didn't respond in time. Your membership is fine. Try again in a minute.", 'signin'),
    'unavailable': ('Activation is temporarily unavailable',
                    "We're finishing setup. Please try again shortly or contact support.", 'support'),
    'not_found': ("This page doesn't exist", 'Check the link, or head back to the activation page.', 'home'),
    'generic': ('Something went wrong',
                'Please try again. If it keeps happening, contact support and include the time it happened.', 'home'),
}

# Errors that can be shown inline on the onboarding page (customer still has a
# valid session, so redirecting back is safe and keeps their progress).
INLINE_KEYS = {k for k, v in MESSAGES.items() if v[2] in ('onboarding', 'support')} - {'unavailable'}


def error_key(detail, status):
    text = str(detail or '')
    for needle, key in DETAIL_KEYS:
        if needle in text:
            return key
    if status == 404:
        return 'not_found'
    return 'generic'


def message_for(key):
    return MESSAGES.get(key or '', None)


def wants_html(request: Request):
    if request.url.path.startswith(JSON_ONLY_PREFIXES):
        return False
    return 'text/html' in request.headers.get('accept', '')


def install(app, render):
    """Register handlers. `render(request, key, status)` returns the error page."""

    def respond(request, key, status):
        if request.method == 'POST' and request.url.path.startswith('/onboarding/') and key in INLINE_KEYS:
            return RedirectResponse(f'/onboarding?error={key}', status_code=303)
        return render(request, key, status)

    @app.exception_handler(StarletteHTTPException)
    async def friendly_http(request: Request, exc: StarletteHTTPException):
        if not wants_html(request):
            return await http_exception_handler(request, exc)
        return respond(request, error_key(exc.detail, exc.status_code), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def friendly_validation(request: Request, exc: RequestValidationError):
        if not wants_html(request):
            return await request_validation_exception_handler(request, exc)
        return respond(request, 'bad_input', 422)
