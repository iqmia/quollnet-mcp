"""Cross-tool instructions advertised by the Quollnet MCP server."""


SERVER_INSTRUCTIONS = """\
Quollnet MCP workflow rules:
- qApp is authoritative for QArticles permissions, validation, publication state, and persistence. Never infer or bypass qApp authorization decisions.
- Before creating a new QArticle or substantially rewriting one, call get_article_authoring_policy and follow the returned policy. Use the planning and approval workflow it defines.
- primary_article_topic is the primary topic. article_topics contains only additional topics and must not repeat the primary topic.
- Creating an article creates an unpublished draft. Do not claim an article is published, approved, or ready for publication unless the corresponding qApp action actually succeeded.
- When editing an existing article, preserve its existing slug unless the user explicitly asks to change it. Legacy slugs are valid when left unchanged.
- Prefer targeted edits for targeted requests. Do not rewrite unrelated article content unless the user asks for a broader rewrite.
- After substantial article edits, use recheck_article. Before publishing or requesting publication, use validate_article_for_publish; resolve hard errors and surface relevant warnings.
- Publication and unpublication outcomes are determined by qApp's normal app-role model. The MCP does not grant author or admin authority.
- Never bulk-replace article links unless the user explicitly requests that replacement and the operation reports what changed.
- Never hard-delete QArticles through MCP. Use archive/restore lifecycle operations when available.
"""
