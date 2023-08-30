from langchain.document_loaders import PyPDFLoader, DirectoryLoader
from langchain import PromptTemplate
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.llms import CTransformers
from langchain.chains import RetrievalQA
import chainlit as cl

# the path of our generated embeddings
DB_FAISS_PATH = 'vectorstores/db_faiss'

# our prompt template
# can be modified for better results
custom_prompt_template = """Use the following pieces of information to answer the user's question.
If you don't know the answer, just say that you don't know, don't try to make up an answer.

Context: {context}
Question: {question}
Image: ![Sadguru](Sadguru.png)  # Insert the image URL here

Only return the helpful answer below and nothing else.
Helpful answer:
"""
# context comes from the LLM

def set_custom_prompt():
    """
    Prompt template for QA retrieval for each vectorstore
    """
    prompt = PromptTemplate(template=custom_prompt_template,input_variables=['context', 'question']) # function from langchain
    # context and the question is passed

    return prompt

#Retrieval QA Chain
# ctransformers have  python bindings form C language and are faster.
def retrieval_qa_chain(llm, prompt, db): # pass the language model,the prompt and the vector db
    qa_chain = RetrievalQA.from_chain_type(llm=llm,
                                       chain_type='stuff',
                                       retriever=db.as_retriever(search_kwargs={'k': 2}),
                                       return_source_documents=True,
                                       chain_type_kwargs={'prompt': prompt}
                                       )
    # return_source doc tells the user from where the source was in the doc passed
    # prompt : key value pair
    return qa_chain

#Loading the model
def load_llm():
    # Load the locally downloaded model here
    llm = CTransformers(
        model = "llama-2-7b-chat.ggmlv3.q8_0.bin",
        model_type="llama",
        max_new_tokens = 512,
        temperature = 0.5
    )
    # the model defined, can be replaced with any ... vicuna,alpaca etc
    # name of model
    # tokens
    # the creativity parameter
    return llm    # return the language model we defined


#QA Model Function
def qa_bot():
    # passing our embeddings
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={'device': 'cpu'})

    # loading the embedding database from local directory
    db = FAISS.load_local(DB_FAISS_PATH, embeddings)

    # load the LLM
    llm = load_llm()

    # Our custom prompt
    qa_prompt = set_custom_prompt()

    # combine the LLM,Prompt and the Vector DB
    qa = retrieval_qa_chain(llm, qa_prompt, db)

    return qa

#output function
def final_result(query):
    qa_result = qa_bot()
    response = qa_result({'query': query})
    response_with_image = f"{response}\n\n![Sadguru](Sadguru.png)"  # Insert the image URL here
    return response_with_image

#chainlit code
@cl.on_chat_start
async def start():
    chain = qa_bot()
    msg = cl.Message(content="Starting the bot...")  # teh msg displayed on user window
    await msg.send()
    msg.content = "Hi, Welcome to SadGuru LLAMA2 Bot. What is your query?"
    await msg.update()

    cl.user_session.set("chain", chain)

@cl.on_message
async def main(message):
    chain = cl.user_session.get("chain")
    cb = cl.AsyncLangchainCallbackHandler(
        stream_final_answer=True, answer_prefix_tokens=["FINAL", "ANSWER"]
    )
    cb.answer_reached = True
    res = await chain.acall(message, callbacks=[cb])
    answer = res["result"]
    sources = res["source_documents"]

    if sources:
        answer += f"\nSources:" + str(sources)
    else:
        answer += "\nNo sources found"

    await cl.Message(content=answer).send()