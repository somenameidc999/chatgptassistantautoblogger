import os
import openai
import time
import csv
from tqdm import tqdm

# Set your OpenAI API key
OPENAI_API_TOKEN = ""
os.environ["OPENAI_API_KEY"] = OPENAI_API_TOKEN

# Initialize the OpenAI client
client = openai.OpenAI()

# Function to upload a file to OpenAI
def upload_file(file_path, purpose):
    with open(file_path, "rb") as file:
        response = client.files.create(file=file, purpose=purpose)
    return response.id

# Upload your files
sitemap_json_id = upload_file('sitemap.json', 'assistants')
# internal_links_file_id = upload_file('internallinks.txt', 'assistants')
# products_file_id = upload_file('products.txt', 'assistants')
# content_plan_file_id = upload_file('2men_it_blog_content_plan_expanded (1).csv', 'assistants')

# Create an Assistant
assistant = client.beta.assistants.create(
    name="Content Creation Assistant",
    model="gpt-3.5-turbo-1106", # gpt-4-1106-preview
    instructions="Every article should have 3 product images minimum. When finding products ensure they are relevant to the specific article you are writing. You must ensure the product image links are written fully and correctly. Every article must have product images. Include at least 3 real product image URLs in the final articles. Choose only relevant product images Do not invent image links. Never invent links or product images Never use sources or footnotes Read sitemap.json - You always choose 5 strictly relevant product images and internal links for the articles. You do not use sources in the outline, you just pick 5 product images that are highly relevant to the article. First you read the attached files and understand them completely, then you create a detailed outline on the blog post topic, including a maximum of 5 HIGHLY relevant internal collection links and product image links. These will finally be used to write an article. Every article shall be written in English. Do not write text in any other language than English",
    tools=[{"type": "retrieval"}],
    # file_ids=[internal_links_file_id, products_file_id, content_plan_file_id]
    file_ids=[sitemap_json_id]
)

def wait_for_run_completion(thread_id, run_id, timeout=300):
    start_time = time.time()
    while time.time() - start_time < timeout:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run_status.status == 'completed':
            return run_status
        time.sleep(10)
    raise TimeoutError("Run did not complete within the specified timeout.")

def get_internal_links(thread_id, blog_post_idea):
    get_request = f"Read the product URLs to find suitable products for articles. Confirm that suitable products are relevant to {blog_post_idea}. Never choose products that are unrrelated to {blog_post_idea}. Never invent links or product images. Choose 5 internal links and 5 product image urls that are relevant to {blog_post_idea}. For example, for exotic leather shoes look for crocodile shoes etc. For suit articles, look for suits. Make sure that when choosing a product that is it related to {blog_post_idea}. Do not choose products that are not related to {blog_post_idea}. Return text in English only. Not other language is to be used other than Engish."
    
    print(get_request)
    
    client.beta.threads.messages.create(thread_id=thread_id, role="user", content=get_request)
    get_request_run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant.id)
    wait_for_run_completion(thread_id, get_request_run.id)
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    return next((m.content for m in messages.data if m.role == "assistant"), [])

def process_blog_post(thread_id, blog_post_idea):
    internal_links = get_internal_links(thread_id, blog_post_idea)
    msgs = ""
    if internal_links is not None:
        for internal_link in internal_links:
            msgs += f"{internal_link.text.value}\n\n"

    outline_request = f"Do not invent image links. use the product images and internal links from {msgs} and use them to create an outline for an article about {blog_post_idea}' In the outline do not use sources or footnotes, but just add a relevant product image in a relevant section, and a relevant internal link in a relevant section. There is no need for a lot of sources, each article needs a maximum of 5 product images and internal links. Return text in English only. Not other language is to be used other than Engish."
    
    client.beta.threads.messages.create(thread_id=thread_id, role="user", content=outline_request)
    outline_run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant.id)
    wait_for_run_completion(thread_id, outline_run.id)
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    outlines = next((m.content for m in messages.data if m.role == "assistant"), None)
    
    outline = ""
    article = ""
    
    if outlines != None:
        for m in outlines: 
            outline += f"{m.text.value}\n\n---"

    if outline:
        article_request = f"Use grade 7 level US English. Return text in English only. Not other language is to be used other than Engish. Do not use overly creative or crazy language. Write as if writing for The Guardian newspaper.. Just give information. Don't write like a magazine. Use simple language. Do not invent image links. You are writing from a first person plural perspective for the business, refer to it in the first person plural. Add a key takeaway table at the top of the article, summarzing the main points. Never invent links or product images. Choose 5 internal links and 5 product images that are relevant to an article and then Write a detailed article based on the following outline:\n{outline}, but put it into a proper title which invites a click, Title should be around 60 characters. Include the product images and internal links naturally and with relevance inside the article. Use markdown formatting and ensure to use tables and lists to add to formatting. Use 3 relevant product images and internal links maximum. Never invent any internal links."
        client.beta.threads.messages.create(thread_id=thread_id, role="user", content=article_request)
        article_run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant.id)
        
        wait_for_run_completion(thread_id, article_run.id)
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        articles = next((m.content for m in messages.data if m.role == "assistant"), None)
        
        if articles != None:
            for m in articles: 
                article += f"{m.text.value}\n\n---"


    return outline, article

def process_content_plan():
    input_file = '2men_it_blog_content_plan_expanded (1).csv'
    output_file = 'processed_content_plan.csv'
    processed_rows = []

    with open(input_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in tqdm(reader, desc="Processing Blog Posts"):
            if row.get('Processed', 'No') == 'Yes':
                continue

            print("Processing")
            blog_post_idea = "Best Men's Pants for 2024" #row['Blog Post Ideas']
            thread_id = client.beta.threads.create().id  # New thread for each blog post
            outline, article = process_blog_post(thread_id, blog_post_idea)
            
            # Make an object like {article: {markdown: article, html: toHtml(article)}, outline: {markdown: outline, html: toHtml(outline)} }

            if outline and article:
                row.update({'Blog Outline': outline, 'Article': article, 'Processed': 'Yes'})
                processed_rows.append(row)

    if len(processed_rows):
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=processed_rows[0].keys())
            writer.writeheader()
            writer.writerows(processed_rows)
        
# Example usage
process_content_plan()
