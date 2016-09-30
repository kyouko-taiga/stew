TransitionSystem

ADT {{ adt }}

Signature

Sorts
    {{ sorts.values()|map('slugify')|sort|join(', ') }}

Generators
    {% for name, (domain, codomain) in signatures.items()|sort(attribute=0) %}
    {{ name }}: {% if domain %}{{ domain|join(', ') }} -> {% endif %}{{ codomain }}
    {% endfor %}

Variables
    {% for identifier, sort in variables %}
    {{ identifier }}: {{ sort }}
    {% endfor %}

Strategies
    __TRS__ = {
        {% for axiom in axioms|sort(attribute='name') %}
        {{ axiom.name|slugify }}({{ axiom.pattern|join(', ') }}) -> {{ axiom.return_value }}{% if not loop.last %},{% endif %}

        {% endfor %}
    }
