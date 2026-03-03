import pandas as pd
import lightanon as la


data = {
    "client_id": [1, 2, 3, 4, 5],
    "card_number": [
        "4444-5555-6666-7777",
        "5555666677778888",
        "9999 0000 1111 2222",
        "1234",
        None,
    ],
    "amount": [1250.0, 50000.0, 320.0, 980000.0, 200.0],
}

df = pd.DataFrame(data)
print("--- ORIGINAL FINANCIAL DATA ---")
print(df)

schema = {
    "card_number": la.financial.CreditCardMask(),
    "amount": la.financial.TopCoding(quantile=0.9),
}

engine = la.Engine(schema)
clean_df = engine.run(df)

print("\n--- ANONYMIZED FINANCIAL DATA ---")
print(clean_df)
print("\n" + engine.generate_report())
