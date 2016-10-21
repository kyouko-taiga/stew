TransitionSystem

ADT {{ adt }}

Signature

Sorts
    {{ sorts|map('nameof')|join(', ') }}

Generators
    {% for name, (domain, codomain) in signatures.items()|sort(attribute=0) %}
    {{ name }}: {% if domain %}{{ domain|join(', ') }} -> {% endif %}{{ codomain }}
    {% endfor %}

Variables
    {% for identifier, sort in variables %}
    {{ identifier }}: {{ sort }}
    {% endfor %}

Strategies
    {% for operation in rules %}
    S_{{ operation|nameof }} = {
        {% for rule in rules[operation] %}
        {{ rule.left }} -> {{ rule.right }}{% if not loop.last %},{% endif %}

        {% endfor %}
    }
    {% endfor %}
