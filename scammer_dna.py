import hashlib
import json
import threading
from collections import Counter
from typing import List, Dict, Any, Tuple, Optional


class ScammerDNA:
    """
    Behavioral fingerprinting engine with in-memory clustering.
    Tracks known signatures, detects repeat scammers via Jaccard similarity,
    and auto-generates cluster labels.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.known_signatures: Dict[str, Dict[str, Any]] = {}
                    cls._instance._cluster_counter = 0
        return cls._instance
    
    @staticmethod
    def jaccard_similarity(set_a: set, set_b: set) -> float:
        """Calculate Jaccard similarity between two sets."""
        if not set_a and not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0
    
    def _generate_cluster_label(self, tactics: List[str], keywords: List[str]) -> str:
        """Auto-generate a human-readable cluster label from tactics and keywords."""
        # Primary label from dominant tactic
        tactic_labels = {
            "urgency": "Urgency",
            "fear": "Fear",
            "authority": "Authority",
            "phishing": "Phishing",
            "financial": "Financial",
        }
        
        # Pick top tactic
        primary = ""
        for t in tactics:
            if t in tactic_labels:
                primary = tactic_labels[t]
                break
        
        if not primary:
            primary = "General"
        
        # Secondary label from keywords
        financial_kw = {"upi", "payment", "transfer", "bank", "account", "kyc"}
        threat_kw = {"blocked", "suspended", "police", "arrest"}
        reward_kw = {"lottery", "prize", "winner", "cashback"}
        
        kw_set = set(k.lower() for k in keywords)
        
        if kw_set & financial_kw:
            secondary = "UPI" if "upi" in kw_set else "Banking"
        elif kw_set & threat_kw:
            secondary = "Threat"
        elif kw_set & reward_kw:
            secondary = "Lottery"
        else:
            secondary = "Scam"
        
        with self._lock:
            self._cluster_counter += 1
            cluster_id = chr(64 + (self._cluster_counter % 26) + 1)  # A, B, C...
        
        return f"{secondary} {primary} Cluster {cluster_id}"
    
    def _find_similar_signature(self, keyword_set: set, tactics_set: set) -> Optional[str]:
        """Find a similar known signature using Jaccard similarity."""
        best_sig = None
        best_score = 0.0
        
        for sig, data in self.known_signatures.items():
            known_keywords = set(data.get("keywords", []))
            known_tactics = set(data.get("tactics", []))
            
            # Combined similarity: weighted keywords + tactics
            kw_sim = self.jaccard_similarity(keyword_set, known_keywords)
            tactic_sim = self.jaccard_similarity(tactics_set, known_tactics)
            combined = 0.6 * kw_sim + 0.4 * tactic_sim
            
            if combined > best_score:
                best_score = combined
                best_sig = sig
        
        if best_score > 0.6:
            return best_sig
        return None
    
    def generate_fingerprint(self, session: Any) -> Tuple[str, Dict[str, Any]]:
        """Create unique behavioral signature from session object."""
        pass  # Use generate_fingerprint_from_history instead

    def generate_fingerprint_from_history(self, history: List[Dict[str, Any]], session_id: str = "") -> Tuple[str, Dict[str, Any]]:
        """
        Generate behavioral fingerprint with clustering support.
        Returns (signature, features_dict) where features_dict includes
        repeat_scammer, cluster_label, and similarity_score.
        """
        keywords = self.extract_keyword_pattern(history)
        timing = self.analyze_timing_pattern(history)
        structure = self.analyze_message_structure(history)
        tactics = self.identify_tactics(history)
        
        features = {
            'keywords': keywords,
            'timing': timing,
            'structure': structure,
            'tactics': tactics,
        }
        
        # Create hash signature
        signature = hashlib.sha256(
            json.dumps(features, sort_keys=True).encode()
        ).hexdigest()[:12]
        
        # === Clustering Logic ===
        keyword_set = set(keywords)
        tactics_set = set(tactics)
        
        similar_sig = self._find_similar_signature(keyword_set, tactics_set)
        
        repeat_scammer = False
        cluster_label = "New Pattern"
        similarity_score = 0.0
        
        if similar_sig and similar_sig in self.known_signatures:
            # Found a similar known scammer
            existing = self.known_signatures[similar_sig]
            repeat_scammer = True
            cluster_label = existing.get("cluster_label", "Unknown Cluster")
            existing["count"] = existing.get("count", 1) + 1
            existing["sessions"].append(session_id)
            
            # Calculate similarity for reporting
            kw_sim = self.jaccard_similarity(keyword_set, set(existing["keywords"]))
            similarity_score = round(kw_sim, 3)
        else:
            # New scammer pattern — create cluster
            cluster_label = self._generate_cluster_label(tactics, keywords)
            self.known_signatures[signature] = {
                "keywords": keywords,
                "tactics": tactics,
                "timing": timing,
                "structure": structure,
                "cluster_label": cluster_label,
                "count": 1,
                "sessions": [session_id],
            }
        
        # Add clustering info to features
        features["repeat_scammer"] = repeat_scammer
        features["cluster_label"] = cluster_label
        features["similarity_score"] = similarity_score
        features["known_patterns_count"] = len(self.known_signatures)
        
        return signature, features
    
    def extract_keyword_pattern(self, history: List[Dict[str, Any]]) -> List[str]:
        """Identify signature keywords from scammer messages."""
        all_text = " ".join([
            msg.get('text', '') for msg in history 
            if msg.get('sender', '').lower() == 'scammer'
        ])
        
        words = all_text.lower().split()
        stopwords = {'the', 'is', 'to', 'and', 'in', 'your', 'of', 'for', 'you', 'a', 'are', 'i', 'my', 'me',
                     'this', 'that', 'it', 'was', 'be', 'have', 'has', 'will', 'can', 'do', 'not', 'please',
                     'with', 'from', 'on', 'at', 'by', 'or', 'an', 'but', 'if', 'so', 'as', 'we', 'they'}
        filtered_words = [w for w in words if w not in stopwords and len(w) > 3]
        
        common_words = Counter(filtered_words).most_common(5)
        return [word for word, count in common_words]
    
    def analyze_timing_pattern(self, history: List[Dict[str, Any]]) -> str:
        """Response time signature classification."""
        if len(history) < 2:
            return "insufficient_data"
        
        gaps = []
        sorted_history = sorted(history, key=lambda x: x.get('timestamp', 0))
        
        for i in range(1, len(sorted_history)):
            curr = sorted_history[i]
            prev = sorted_history[i-1]
            
            if curr.get('sender', '').lower() == 'scammer' and prev.get('sender', '').lower() != 'scammer':
                gap = (curr.get('timestamp', 0) - prev.get('timestamp', 0)) / 1000.0
                if gap > 0:
                    gaps.append(gap)
        
        if not gaps:
            return "no_pattern"
        
        avg_gap = sum(gaps) / len(gaps)
        
        if avg_gap < 5:
            return "automated_fast"
        elif avg_gap < 45:
            return "human_responsive"
        else:
            return "human_slow"
            
    def analyze_message_structure(self, history: List[Dict[str, Any]]) -> str:
        """Analyze if messages are short/long/mixed."""
        scammer_msgs = [m.get('text', '') for m in history if m.get('sender', '').lower() == 'scammer']
        if not scammer_msgs:
            return "unknown"
            
        avg_len = sum(len(m) for m in scammer_msgs) / len(scammer_msgs)
        if avg_len < 30: return "short_bursts"
        if avg_len > 100: return "long_scripts"
        return "balanced"
    
    def identify_tactics(self, history: List[Dict[str, Any]]) -> List[str]:
        """Scam tactic identification across full conversation."""
        tactics = []
        all_text = " ".join([m.get('text', '') for m in history]).lower()
        
        if any(word in all_text for word in ['urgent', 'immediately', 'now', 'today', 'hurry', 'fast']):
            tactics.append('urgency')
        if any(word in all_text for word in ['blocked', 'suspended', 'expired', 'police', 'illegal', 'arrest', 'court']):
            tactics.append('fear')
        if any(word in all_text for word in ['verify', 'confirm', 'update', 'submit', 'official']):
            tactics.append('authority')
        if 'http' in all_text or '.com' in all_text or 'link' in all_text or 'click' in all_text:
            tactics.append('phishing')
        if any(word in all_text for word in ['upi', 'pay', 'transfer', 'amount', 'rs', 'rupees', 'bank']):
            tactics.append('financial')
        if any(word in all_text for word in ['won', 'prize', 'lottery', 'reward', 'cashback']):
            tactics.append('reward')
        
        return list(set(tactics))
    
    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get clustering statistics for metrics."""
        clusters = {}
        for sig, data in self.known_signatures.items():
            label = data.get("cluster_label", "Unknown")
            if label not in clusters:
                clusters[label] = {"count": 0, "sessions": []}
            clusters[label]["count"] += data.get("count", 1)
            clusters[label]["sessions"].extend(data.get("sessions", []))
        
        return {
            "total_signatures": len(self.known_signatures),
            "clusters": clusters
        }
