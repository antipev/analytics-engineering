{% materialization raw_sql, adapter='duckdb' %}
    {%- set identifier = model['alias'] -%}
    {%- set target_relation = api.Relation.create(database=database, schema=schema, identifier=identifier) -%}

    {{ run_hooks(pre_hooks) }}

    {% call statement('main') -%}
        {{ sql }}
    {% endcall -%}

    {{ run_hooks(post_hooks) }}

    {{ return({'relations': [target_relation]}) }}
{% endmaterialization %}
