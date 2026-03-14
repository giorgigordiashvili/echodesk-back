import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(soft_time_limit=120, time_limit=180)
def generate_invoice_pdf(schema_name, invoice_id):
    from tenant_schemas.utils import schema_context
    from invoices.models import Invoice

    with schema_context(schema_name):
        invoice = Invoice.objects.get(id=invoice_id)
        invoice.generate_pdf()
        logger.info(f'generate_invoice_pdf({schema_name}, {invoice_id}) completed')
        return str(invoice.pdf_file.url) if invoice.pdf_file else None
