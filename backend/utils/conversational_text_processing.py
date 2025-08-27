# utils/conversational_text_processing.py
"""
Conversational AI text processing utilities for IntraNest 2.0
This is separate from the document processing utilities in text_processing.py
"""

import re
import openai
from typing import Dict, List, Any, Optional
from models.conversation_models import ConversationIntent
import logging

logger = logging.getLogger(__name__)

class ConversationalTextProcessor:
    """Enhanced text processing for conversational RAG"""
    
    def __init__(self, openai_client: openai.AsyncOpenAI, config: Dict[str, Any]):
        self.openai = openai_client
        self.config = config
        self.classification_model = config.get("classification_model", "gpt-3.5-turbo")
        
        # Intent classification patterns
        self.intent_patterns = {
            ConversationIntent.DEFINITION: [
                r'\bwhat is\b', r'\bdefine\b', r'\bexplain\b', r'\bmean\b',
                r'\bdefinition of\b', r'\bwhat does.*mean\b'
            ],
            ConversationIntent.IMPROVEMENT: [
                r'\bhow.*improve\b', r'\bways to.*better\b', r'\benhance\b',
                r'\boptimize\b', r'\bbetter\b', r'\bupgrade\b'
            ],
            ConversationIntent.EXPANSION: [
                r'\bexpand on\b', r'\bmore about\b', r'\btell me more\b',
                r'\belaborate\b', r'\bdetails\b', r'\bin depth\b'
            ],
            ConversationIntent.EXPLANATION: [
                r'\bhow does\b', r'\bwhy\b', r'\bhow to\b', r'\bprocess\b',
                r'\bwork\b', r'\bfunction\b', r'\boperate\b'
            ],
            ConversationIntent.SUMMARIZATION: [
                r'\bsummarize\b', r'\bsummary\b', r'\boverview\b',
                r'\bmain points\b', r'\bkey.*points\b'
            ]
        }
    
    async def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract named entities from text using LLM"""
        try:
            prompt = f"""Extract key entities from this text. Focus on:
- Companies/Organizations
- Technologies
- Products/Services  
- People
- Locations
- Concepts

Text: "{text}"

Return entities as JSON with entity_type as key and entity_name as value.
Example: {{"company": "TCS", "technology": "AI", "concept": "cybersecurity"}}

JSON:"""

            response = await self.openai.chat.completions.create(
                model=self.classification_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            result = response.choices[0].message.content.strip()
            
            # Try to parse JSON
            import json
            try:
                entities = json.loads(result)
                return entities if isinstance(entities, dict) else {}
            except json.JSONDecodeError:
                # Fallback to simple extraction
                return self._simple_entity_extraction(text)
                
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return self._simple_entity_extraction(text)
    
    def _simple_entity_extraction(self, text: str) -> Dict[str, Any]:
        """Simple rule-based entity extraction as fallback"""
        entities = {}
        text_upper = text.upper()
        
        # Common company acronyms
        company_patterns = [
            r'\b(TCS|IBM|MICROSOFT|GOOGLE|AMAZON|APPLE)\b',
            r'\b([A-Z]{2,5}(?:\s+[A-Z]{2,5})?)\b'  # General acronyms
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, text_upper)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if len(match) >= 2:
                    entities["organization"] = match
                    break
        
        # Technology keywords
        tech_keywords = ['AI', 'ARTIFICIAL INTELLIGENCE', 'MACHINE LEARNING', 
                        'BLOCKCHAIN', 'CLOUD', 'CYBERSECURITY', 'IOT']
        
        for keyword in tech_keywords:
            if keyword in text_upper:
                entities["technology"] = keyword.lower().replace(' ', '_')
                break
        
        return entities
    
    async def classify_intent(self, text: str) -> ConversationIntent:
        """Classify user intent from text"""
        text_lower = text.lower()
        
        # Rule-based classification first (faster)
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent
        
        # Fallback to LLM classification for complex cases
        try:
            prompt = f"""Classify the intent of this user message:

"{text}"

Choose from these categories:
- definition: asking what something is or means
- improvement: asking how to make something better
- expansion: asking for more details or elaboration  
- explanation: asking how something works or why
- summarization: asking for a summary or overview
- clarification: asking for clarification
- general: general conversation or other

Return only the category name:"""

            response = await self.openai.chat.completions.create(
                model=self.classification_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=20
            )
            
            result = response.choices[0].message.content.strip().lower()
            
            # Map to enum
            intent_mapping = {
                "definition": ConversationIntent.DEFINITION,
                "improvement": ConversationIntent.IMPROVEMENT,
                "expansion": ConversationIntent.EXPANSION,
                "explanation": ConversationIntent.EXPLANATION,
                "summarization": ConversationIntent.SUMMARIZATION,
                "clarification": ConversationIntent.CLARIFICATION,
                "general": ConversationIntent.GENERAL
            }
            
            return intent_mapping.get(result, ConversationIntent.GENERAL)
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return ConversationIntent.GENERAL
    
    async def extract_topic(self, text: str) -> Optional[str]:
        """Extract main topic from text"""
        try:
            prompt = f"""Extract the main topic or subject from this text in 2-4 words:

"{text}"

Topic:"""

            response = await self.openai.chat.completions.create(
                model=self.classification_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=30
            )
            
            topic = response.choices[0].message.content.strip()
            return topic if len(topic) > 2 else None
            
        except Exception as e:
            logger.error(f"Topic extraction failed: {e}")
            return None
    
    async def summarize_conversation(self, messages: List[Dict[str, Any]]) -> str:
        """Generate summary of conversation messages"""
        try:
            # Format messages for summarization
            conversation_text = ""
            for msg in messages:
                role = msg.get("role", "").upper()
                content = msg.get("content", "")
                conversation_text += f"{role}: {content}\n"
            
            prompt = f"""Summarize this conversation concisely, focusing on:
- Main topics discussed
- Key information shared
- Important decisions or conclusions
- Unresolved questions

Conversation:
{conversation_text}

Summary:"""

            response = await self.openai.chat.completions.create(
                model=self.classification_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Conversation summarization failed: {e}")
            return "Unable to generate summary"
    
    def detect_topic_change(self, current_message: str, previous_topic: Optional[str]) -> bool:
        """Detect if conversation topic has changed"""
        if not previous_topic:
            return False
        
        current_lower = current_message.lower()
        previous_lower = previous_topic.lower()
        
        # Topic change indicators
        change_indicators = [
            r'\blet\'s talk about\b', r'\bchanging topics?\b', r'\bmove on to\b',
            r'\bnext topic\b', r'\bdifferent question\b', r'\banother topic\b'
        ]
        
        for indicator in change_indicators:
            if re.search(indicator, current_lower):
                return True
        
        # Check if current message contains previous topic
        # If not, it might be a topic change
        topic_words = previous_lower.split()
        topic_matches = sum(1 for word in topic_words if word in current_lower)
        
        # If less than 30% of topic words are present, consider it a change
        if len(topic_words) > 0 and topic_matches / len(topic_words) < 0.3:
            return True
        
        return False
    
    def clean_conversational_text(self, text: str) -> str:
        """Clean and normalize conversational text (different from document cleaning)"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        
        # Normalize quotes
        text = re.sub(r'[""''``]', '"', text)
        
        return text.strip()
    
    def extract_key_phrases(self, text: str, max_phrases: int = 5) -> List[str]:
        """Extract key phrases from text using simple heuristics"""
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        
        key_phrases = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:  # Skip very short sentences
                continue
            
            # Look for phrases with important keywords
            important_patterns = [
                r'\b(?:AI|artificial intelligence|machine learning)\b.*?(?:[.!?]|$)',
                r'\b(?:improve|enhance|optimize)\s+\w+.*?(?:[.!?]|$)',
                r'\b(?:capabilities?|features?|benefits?)\b.*?(?:[.!?]|$)',
                r'\b(?:solution|system|platform)\b.*?(?:[.!?]|$)'
            ]
            
            for pattern in important_patterns:
                matches = re.findall(pattern, sentence, re.IGNORECASE)
                key_phrases.extend(matches)
                
                if len(key_phrases) >= max_phrases:
                    break
            
            if len(key_phrases) >= max_phrases:
                break
        
        # Clean and deduplicate
        cleaned_phrases = []
        for phrase in key_phrases[:max_phrases]:
            cleaned = self.clean_conversational_text(phrase)
            if cleaned and cleaned not in cleaned_phrases:
                cleaned_phrases.append(cleaned)
        
        return cleaned_phrases
    
    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity using word overlap"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
