from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "ziad1662004"

try:
    print(f"Connecting to {URI} as {USER}...")

    driver = GraphDatabase.driver(
        URI,
        auth=(USER, PASSWORD)
    )

    driver.verify_connectivity()
    print("✅ Connectivity verified")

    with driver.session() as session:
        result = session.run("RETURN 'Hello Neo4j' AS msg")
        record = result.single()
        print("✅ Query succeeded")
        print("Result:", record["msg"])

    driver.close()

except AuthError as e:
    print("❌ Authentication failed")
    print(e)

except ServiceUnavailable as e:
    print("❌ Neo4j server is not reachable")
    print(e)

except Exception as e:
    print("❌ Unexpected error")
    print(type(e).__name__)
    print(e)