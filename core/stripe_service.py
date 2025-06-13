import os
import logging
import stripe
from django.conf import settings
from django.urls import reverse

# Configure logging
logger = logging.getLogger(__name__)

# Get Stripe API key from environment
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
stripe.api_key = STRIPE_SECRET_KEY

# Fee amount in rupees (needs to be converted to paisa for Stripe)
STUDENT_REGISTRATION_FEE_INR = 1000
STUDENT_REGISTRATION_FEE_PAISA = STUDENT_REGISTRATION_FEE_INR * 100  # Convert to paisa

def create_checkout_session(request, user_id=None):
    """
    Create a Stripe checkout session for student registration payment
    
    Args:
        request: The HTTP request
        user_id: Optional user ID if the user has already been partially registered
        
    Returns:
        dict: Dictionary containing checkout session ID and URL
    """
    try:
        # Create the product if it doesn't exist
        products = stripe.Product.list(limit=100)
        product_id = None
        
        for product in products.data:
            if product.name == 'the360learning Student Registration':
                product_id = product.id
                break
        
        if not product_id:
            # Create a new product
            product = stripe.Product.create(
                name='the360learning Student Registration',
                description='Student registration fee for the360learning platform'
            )
            product_id = product.id
        
        # Create the price if it doesn't exist
        prices = stripe.Price.list(limit=100, product=product_id)
        price_id = None
        
        for price in prices.data:
            # Find a price with the correct amount
            if price.unit_amount == STUDENT_REGISTRATION_FEE_PAISA and price.currency == 'inr':
                price_id = price.id
                break
        
        if not price_id:
            # Create a new price
            price = stripe.Price.create(
                product=product_id,
                unit_amount=STUDENT_REGISTRATION_FEE_PAISA,
                currency='inr',
                nickname='Standard Registration Fee'
            )
            price_id = price.id
        
        # Determine success and cancel URLs
        domain_url = request.build_absolute_uri('/').rstrip('/')
        success_url = domain_url + reverse('payment_success')
        cancel_url = domain_url + reverse('payment_cancel')
        
        # Add user ID as metadata if provided
        metadata = {}
        if user_id:
            metadata['user_id'] = str(user_id)
        
        # Create the checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata=metadata,
        )
        
        return {
            'id': checkout_session.id,
            'url': checkout_session.url
        }
    
    except Exception as e:
        logger.error(f"Error creating Stripe checkout session: {str(e)}")
        return None

def verify_checkout_session(session_id):
    """
    Verify a completed checkout session
    
    Args:
        session_id: The Stripe checkout session ID
        
    Returns:
        dict: Dictionary containing payment status and metadata
    """
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        return {
            'status': checkout_session.payment_status,
            'metadata': checkout_session.metadata,
            'customer_email': checkout_session.customer_details.email if checkout_session.customer_details else None,
            'amount_total': checkout_session.amount_total / 100,  # Convert from paisa to rupees
            'currency': checkout_session.currency
        }
    
    except Exception as e:
        logger.error(f"Error verifying Stripe checkout session: {str(e)}")
        return None

def handle_stripe_webhook(payload, sig_header):
    """
    Handle Stripe webhook events
    
    Args:
        payload: The webhook payload
        sig_header: The Stripe signature header
        
    Returns:
        dict: Dictionary containing event details
    """
    try:
        # Get webhook secret from environment
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        
        if webhook_secret:
            # Verify the webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # If no webhook secret, just parse the payload
            event = stripe.Event.construct_from(
                payload, stripe.api_key
            )
        
        # Handle specific event types
        if event.type == 'checkout.session.completed':
            checkout_session = event.data.object
            
            # Safe extraction of values with default fallbacks
            amount_total = getattr(checkout_session, 'amount_total', 0)
            amount_total_rupees = amount_total / 100 if amount_total else 0
            
            # Safely access nested attributes
            customer_email = None
            if hasattr(checkout_session, 'customer_details') and checkout_session.customer_details:
                customer_email = getattr(checkout_session.customer_details, 'email', None)
            
            return {
                'event_type': event.type,
                'status': getattr(checkout_session, 'payment_status', 'unknown'),
                'metadata': getattr(checkout_session, 'metadata', {}),
                'customer_email': customer_email,
                'amount_total': amount_total_rupees,
                'currency': getattr(checkout_session, 'currency', 'inr')
            }
        
        return {
            'event_type': event.type
        }
    
    except Exception as e:
        logger.error(f"Error handling Stripe webhook: {str(e)}")
        return None