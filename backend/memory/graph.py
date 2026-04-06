from neo4j import AsyncGraphDatabase
from backend.config import get_settings

settings = get_settings()


class GraphMemory:
    def __init__(self):
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    async def close(self):
        await self._driver.close()

    async def upsert_entity(self, name: str, entity_type: str, properties: dict = {}):
        async with self._driver.session() as session:
            await session.run(
                f"MERGE (e:{entity_type} {{name: $name}}) SET e += $props",
                name=name, props=properties,
            )

    async def upsert_relation(self, from_name: str, relation: str, to_name: str):
        async with self._driver.session() as session:
            await session.run(
                f"""
                MATCH (a {{name: $from_name}}), (b {{name: $to_name}})
                MERGE (a)-[:{relation}]->(b)
                """,
                from_name=from_name, to_name=to_name,
            )

    async def query_entity(self, name: str) -> list[dict]:
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (e {name: $name})-[r]-(related) RETURN type(r) as rel, related.name as name, labels(related) as types",
                name=name,
            )
            return [dict(record) async for record in result]

    async def get_context_for(self, entities: list[str]) -> str:
        if not entities:
            return ""
        results = []
        for entity in entities[:5]:
            relations = await self.query_entity(entity)
            for r in relations:
                results.append(f"{entity} {r['rel']} {r['name']}")
        return "\n".join(results)
