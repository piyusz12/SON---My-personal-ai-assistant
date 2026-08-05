from memory import Memory

if __name__ == "__main__":
    mem = Memory()
    mem.store_fact("My favorite language is Python.", category="preferences")
    result = mem.recall_facts("Which programming language do I like?")
    print("Recalled facts:", result)