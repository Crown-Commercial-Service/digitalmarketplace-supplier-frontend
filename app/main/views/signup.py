from flask import render_template
from app.main import main
from react.render import render_component


@main.route('/signup')
def start_seller_signup():
    rendered_component = render_component(
        'bundles/SellerRegistration/StartWidget.js',
        {
            'deed': '/buyers-guide',
            'signup': '#'
        }
    )

    return render_template(
        '_react.html',
        component=rendered_component
    )
