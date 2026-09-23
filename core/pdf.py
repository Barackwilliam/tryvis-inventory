"""
Documents render as print-ready HTML. If xhtml2pdf is installed the same
template is also served as a real PDF, which is what you want when the
invoice has to be emailed rather than handed over the counter.
"""
from io import BytesIO

from django.http import HttpResponse
from django.template.loader import render_to_string


def render_pdf(template_name, context, filename):
    html = render_to_string(template_name, context)
    try:
        from xhtml2pdf import pisa
    except ImportError:
        response = HttpResponse(html)
        response["X-PDF-Fallback"] = "xhtml2pdf not installed - served as HTML"
        return response

    buffer = BytesIO()
    result = pisa.CreatePDF(html, dest=buffer, encoding="utf-8")
    if result.err:
        return HttpResponse(html)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
