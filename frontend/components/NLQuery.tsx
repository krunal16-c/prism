"use client";

import { useState } from "react";
import axios from "axios";
import { Search, Loader2, Sparkles, ArrowRight, Database, Globe } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";

interface NLQueryProps {
  onResults: (results: any[], dataSource?: string) => void;
}

export default function NLQuery({ onResults }: NLQueryProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [interpretation, setInterpretation] = useState<string | null>(null);
  const [dataSource, setDataSource] = useState<string | null>(null);
  const [resultCount, setResultCount] = useState<number | null>(null);
  const [isFocused, setIsFocused] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setInterpretation(null);
    setDataSource(null);
    setResultCount(null);

    try {
      const response = await axios.post("http://localhost:8000/api/query/nl", {
        query: query,
      });
      
      setInterpretation(response.data.interpretation);
      setDataSource(response.data.data_source);
      setResultCount(response.data.result_count);
      
      if (response.data.results) {
        onResults(response.data.results, response.data.data_source);
      }
    } catch (error) {
      console.error("Error querying:", error);
      setInterpretation("System error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full relative group">
      <motion.div 
        animate={{ 
          scale: isFocused ? 1.02 : 1,
          boxShadow: isFocused ? "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)" : "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)"
        }}
        className={clsx(
          "relative bg-white/80 backdrop-blur-xl rounded-2xl border transition-colors overflow-hidden",
          isFocused ? "border-blue-500/50 bg-white" : "border-slate-200/60 hover:border-slate-300"
        )}
      >
        <form onSubmit={handleSearch} className="flex items-center p-1">
          <div className="pl-4 pr-3 text-slate-400">
            {loading ? (
              <Loader2 className="animate-spin text-blue-600" size={20} />
            ) : (
              <Search size={20} className={clsx(isFocused && "text-blue-600")} />
            )}
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="Ask PRISM... (e.g., 'Show critical bridges in Nova Scotia')"
            className="flex-1 bg-transparent border-none outline-none py-3 text-slate-900 placeholder:text-slate-400 font-medium"
          />
          <div className="pr-2">
            <button 
              type="submit"
              disabled={!query.trim() || loading}
              className={clsx(
                "p-2 rounded-xl transition-all duration-200 flex items-center gap-2",
                query.trim() && !loading
                  ? "bg-blue-600 text-white shadow-md shadow-blue-600/20 hover:bg-blue-700" 
                  : "bg-slate-100 text-slate-300 cursor-not-allowed"
              )}
            >
              {loading ? <span className="text-xs font-semibold px-1">Processing</span> : <ArrowRight size={18} />}
            </button>
          </div>
        </form>

        {/* AI Interpretation Result */}
        <AnimatePresence>
          {interpretation && (
            <motion.div 
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="border-t border-slate-100 bg-slate-50/50"
            >
              <div className="p-3 px-4 flex items-start gap-3 text-sm text-slate-600">
                <Sparkles size={16} className="mt-0.5 text-blue-600 shrink-0" />
                <div className="flex-1">
                  <p className="leading-relaxed">
                    <span className="font-semibold text-slate-900">Analysis:</span> {interpretation}
                  </p>
                  {dataSource && resultCount !== null && (
                    <div className="mt-2 flex items-center gap-2 text-xs">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full ${
                        dataSource === 'bridges' 
                          ? 'bg-green-100 text-green-700' 
                          : 'bg-blue-100 text-blue-700'
                      }`}>
                        {dataSource === 'bridges' ? <Database size={12} /> : <Globe size={12} />}
                        {dataSource === 'bridges' ? 'Government Bridge Data' : 'Asset Database'}
                      </span>
                      <span className="text-slate-500">
                        {resultCount} result{resultCount !== 1 ? 's' : ''} found
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
      
      {/* Helper hint - shows above the search bar */}
      <AnimatePresence>
        {isFocused && !interpretation && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="absolute bottom-full left-0 w-full mb-2 p-2"
          >
            <div className="bg-slate-900/80 backdrop-blur-md text-white text-xs py-1.5 px-3 rounded-lg inline-flex flex-wrap gap-2 shadow-lg">
              <span>Try:</span>
              <span className="text-blue-300">"Show critical bridges in BC"</span>
              <span className="text-slate-400">•</span>
              <span className="text-green-300">"Poor condition bridges in Ontario"</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
