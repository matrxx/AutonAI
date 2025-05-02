# AutonAI

// The project is in "standby" mode because I realized that I need a way bigger hardware to make it the way I want it (something like 40GB of VRAM to run the LLMs locally. So i'll wait for the open sources models to make lighter llms that fits my needs.

1. Install Ollama via https://ollama.com/ and wamp via https://wampserver.aviatechno.net/ (+ all the packages)
2. Install everything in the useful.txt via a pip install
3. Run the OllamaSetup.exe and make sure it's running before doing next
4. Run "dl_llama2.py" to install a local version of the agent ((ollama pull codellama:34b-instruct-q4_K_M))
5. Run "test_" to check if the AI agent is ready to run *not set yet*
6. Adapt structure : put the html/css/js files in www/ from wamp and the py files elsewhere
7. Run "agent.py" to start the LLM
8. Go to http://localhost/AutonAI/index.html on your web browser to start using AutonAI

![AutonAI - Illustration](https://github.com/user-attachments/assets/9c570997-507b-499e-80d9-052e565c7ac7)

# Current Advancement
![Progress](https://img.shields.io/badge/Progress-20%25-blue)


Major issues : 

- Upgrading the LLM requires to handle the VRAM charge which is important
- The goal is to keep it accessible to majority of the hardware
- Having the expected result takes times

# Roadmap:
*for the roadmap basically eveything is under the radar but the points with the 🛠️ emoji means that it is the priority*

• Better website design

  --> Charge bar for the project updates in real time
  
  --> Better webste ergonomy (button placement/size, responsive, etc)
  
  --> Night mode ☑️
  
  --> Branding (logo, identity, favicon, font) 🛠️
  
  --> Animated? (agents tasks representations) *secondary*
  

• Better console

  --> Upgrade the console looks
  
  --> Fix the fetching errors 🛠️
  
  --> Fix the "tool" error ☑️
  

• Better autonomous agents

  --> Fix the problems and make everything working as intended 🛠️
  
  --> Make them upload the final render on the web to get the work 🛠️
  

• Better LLM

  --> LLM upgrade to boost the overall AI framework of AutonAI (currently implementing Llama3.3) 🛠️
  
  --> Optimize it for the multiple agent tasks

  --> Multi LLM integration to make them interact
  

• And more

--> Multi language support

--> Tools integration (jobs focus optimized)

--> Multi AI powered interconnected tools for IT (graphana, kibana, elasticsearch, powerBI, etc..)

--> Multi AI powered interconnected tools for collaboration tools (teams, slack, trello, etc...)

--> Preview of the work done in real time
