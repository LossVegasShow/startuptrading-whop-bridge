"""HTML versions of customer emails.

Email clients ignore stylesheets, so everything is inline and table-based.
Plain-text versions are always sent alongside these.
"""
from html import escape

BG = '#07090d'
CARD = '#10151d'
LINE = '#1f2733'
TEXT = '#e8ecf2'
MUTED = '#8a96a8'
ACCENT = '#fa7b39'
OK = '#3ddc97'
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,'SF Mono',Menlo,Consolas,monospace"


def _shell(preheader, body, support_email=''):
    support = (f'Questions? Reply to this email or write to '
               f'<a href="mailto:{escape(support_email)}" style="color:{ACCENT}">{escape(support_email)}</a>.'
               if support_email else 'Questions? Reply to this email.')
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark"></head>
<body style="margin:0;padding:0;background:{BG}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}">
<tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px">
<tr><td style="padding:0 4px 18px;font:700 13px {SANS};letter-spacing:.08em;color:{TEXT}">
<span style="color:{ACCENT}">&#9646;</span> STARTUPTRADING</td></tr>
<tr><td style="background:{CARD};border:1px solid {LINE};border-radius:10px;padding:32px 28px;font:15px/1.6 {SANS};color:{TEXT}">
{body}
</td></tr>
<tr><td style="padding:18px 4px 0;font:12.5px/1.6 {SANS};color:{MUTED}">{support}<br>
We never ask for your NinjaTrader or Whop password.</td></tr>
</table></td></tr></table></body></html>'''


def code_email(code, support_email=''):
    digits = escape(str(code))
    body = f'''<p style="margin:0 0 6px;font:600 11.5px {MONO};letter-spacing:.08em;color:{ACCENT}">VERIFICATION CODE</p>
<h1 style="margin:0 0 14px;font:650 22px/1.3 {SANS};color:{TEXT}">Your activation code</h1>
<p style="margin:0 0 20px;color:#b4bdca">Enter this code on the StartUpTrading activation page.</p>
<div style="background:{BG};border:1px solid {LINE};border-radius:8px;padding:18px;text-align:center;
font:700 32px {MONO};letter-spacing:.35em;color:{TEXT}">{digits}</div>
<p style="margin:20px 0 0;font-size:13.5px;color:{MUTED}">The code expires in 10 minutes. If you didn't request it, you can ignore this email.</p>'''
    return _shell(f'Your code is {code}. It expires in 10 minutes.', body, support_email)


def activation_email(nt_email, indicator_names, setup_url, discord_url='', support_email=''):
    rows = ''.join(
        f'<tr><td style="padding:12px 14px;border-top:1px solid {LINE};font:600 14.5px {SANS};color:{TEXT}">{escape(n)}</td>'
        f'<td align="right" style="padding:12px 14px;border-top:1px solid {LINE};font:600 11.5px {MONO};color:{OK}">&#9679; ACTIVE</td></tr>'
        for n in indicator_names)
    discord = (f'<a href="{escape(discord_url)}" style="display:inline-block;margin-left:8px;padding:13px 20px;border:1px solid #2c3644;'
               f'border-radius:8px;color:{TEXT};font:600 14.5px {SANS};text-decoration:none">Join the Discord</a>'
               if discord_url else '')
    body = f'''<p style="margin:0 0 6px;font:600 11.5px {MONO};letter-spacing:.08em;color:{OK}">&#10003; ACTIVATED</p>
<h1 style="margin:0 0 14px;font:650 24px/1.25 {SANS};color:{TEXT}">Your indicators are ready.</h1>
<p style="margin:0 0 20px;color:#b4bdca">All three StartUpTrading indicators are licensed to your NinjaTrader account
<strong style="color:{TEXT}">{escape(nt_email)}</strong>.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};border:1px solid {LINE};border-radius:8px;border-collapse:separate">
<tr><td colspan="2" style="padding:10px 14px;font:600 11px {MONO};letter-spacing:.06em;color:{MUTED}">YOUR INDICATORS</td></tr>
{rows}</table>
<p style="margin:26px 0 8px;font:650 15px {SANS};color:{TEXT}">Finish setup in NinjaTrader</p>
<ol style="margin:0 0 24px;padding-left:20px;color:#b4bdca">
<li style="margin-bottom:6px">Open NinjaTrader and sign in with {escape(nt_email)}.</li>
<li style="margin-bottom:6px">Follow the install guide to import the indicators.</li>
<li>Add them to a chart. If one doesn't show up, restart NinjaTrader once before contacting support.</li></ol>
<a href="{escape(setup_url)}" style="display:inline-block;padding:13px 20px;background:{ACCENT};border-radius:8px;
color:#160b04;font:600 14.5px {SANS};text-decoration:none">Open install guide &rarr;</a>{discord}
<p style="margin:26px 0 0;font-size:13.5px;color:{MUTED}">Access stays active while your Whop membership is active.
Please contact support before buying a second subscription if anything looks wrong.</p>'''
    return _shell('All three indicators are licensed to your NinjaTrader account.', body, support_email)


def _button(url, label):
    return (f'<a href="{escape(url)}" style="display:inline-block;padding:13px 20px;background:{ACCENT};border-radius:8px;'
            f'color:#160b04;font:600 14.5px {SANS};text-decoration:none">{escape(label)} &rarr;</a>')


def _body(eyebrow, color, title, paragraphs, button=None):
    ps = ''.join(f'<p style="margin:0 0 14px;color:#b4bdca">{p}</p>' for p in paragraphs)
    return (f'<p style="margin:0 0 6px;font:600 11.5px {MONO};letter-spacing:.08em;color:{color}">{escape(eyebrow)}</p>'
            f'<h1 style="margin:0 0 16px;font:650 22px/1.3 {SANS};color:{TEXT}">{escape(title)}</h1>{ps}'
            + (f'<div style="margin-top:22px">{button}</div>' if button else ''))


def reminder_email(first, activation_url, support_email=''):
    """Activation reminder (24 h, then 72 h). Returns (text, html)."""
    if first:
        title = 'Your indicators are waiting'
        lines = ['Thanks for joining StartUpTrading. Your three NinjaTrader indicators are ready to be licensed, '
                 'and it takes about three minutes.',
                 'Sign in with the Whop account you used to join, then confirm the email on your NinjaTrader '
                 'account with a 6-digit code. No NinjaTrader account yet? You can create a free one during setup.']
    else:
        title = 'Need a hand activating?'
        lines = ["Your StartUpTrading membership is active, but your indicators aren't connected to NinjaTrader yet.",
                 'If something got in the way (a missing code, a different email on your NinjaTrader account, '
                 'or no account yet), reply to this email and we\'ll sort it out with you.']
    text = '\n\n'.join([title] + lines + [f'Activate: {activation_url}'] +
                        ([f'Support: {support_email}'] if support_email else []))
    html = _shell(lines[0], _body('ACTIVATION', ACCENT, title, [escape(l) for l in lines],
                                  _button(activation_url, 'Activate my indicators')), support_email)
    return text, html


def ending_email(when, hub_url='', support_email=''):
    """Cancelled, still paid up. Returns (text, html)."""
    lines = [f'Your StartUpTrading membership is set to end on {when}. Until then you keep full access to all '
             'three indicators and the Discord.',
             'After that date the indicators switch off automatically in NinjaTrader. If you change your mind, '
             'you can keep your membership from your Whop account, and nothing changes.']
    text = '\n\n'.join([f'Your access ends on {when}'] + lines +
                        ([f'Manage your membership: {hub_url}'] if hub_url else []) +
                        ([f'Support: {support_email}'] if support_email else []))
    html = _shell(lines[0], _body('MEMBERSHIP', ACCENT, f'Your access ends on {when}', [escape(l) for l in lines],
                                  _button(hub_url, 'Manage my membership') if hub_url else None), support_email)
    return text, html


def ended_email(rejoin_url, support_email=''):
    """Membership ended. Returns (text, html)."""
    lines = ['Your StartUpTrading membership has ended, so your three indicators have been switched off in '
             'NinjaTrader and Discord access has closed.',
             "You're welcome back any time. Rejoin and reconnect with the same NinjaTrader account, and the "
             'indicators come straight back.']
    text = '\n\n'.join(['Your indicators have been switched off'] + lines + [f'Rejoin: {rejoin_url}'] +
                        ([f'Support: {support_email}'] if support_email else []))
    html = _shell(lines[0], _body('MEMBERSHIP', MUTED, 'Your indicators have been switched off',
                                  [escape(l) for l in lines], _button(rejoin_url, 'Rejoin StartUpTrading')),
                  support_email)
    return text, html
