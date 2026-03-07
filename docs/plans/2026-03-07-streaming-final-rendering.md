# Streaming Final Rendering Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make tool-calling reasoner turns stream when the provider supports it, and stop the CLI from re-printing a final answer that was already streamed live.

**Architecture:** Keep the existing provider event interface. Change the LangChain provider client to attempt `model.stream(...)` even when tools are bound, aggregate streamed chunks into the same normalized response shape, and only fall back to `invoke(...)` when the stream yields neither text nor tool calls. In the CLI, keep the existing live stream line, buffer the most recent streamed text, and suppress duplicate final printing when that buffer matches the final reply.

**Tech Stack:** Python, pytest, LangChain provider adapter, TeamBot CLI.

---
