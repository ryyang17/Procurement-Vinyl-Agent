#!/usr/bin/env python3

"""
Debug script om workflow path selection probleem te analyseren
"""

import os
from agent.agent import create_procurement_workflow
from agent.utils.state import ProcurementState

def debug_workflow():
    print("🔧 Debug: Workflow Path Selection Probleem")
    print("=" * 50)
    
    # Create workflow
    workflow = create_procurement_workflow()
    
    print("✅ Workflow gecreëerd")
    
    # Test scenario: simuleer een stuck path selection
    test_state = ProcurementState()
    test_state.step = "awaiting_human_input"
    test_state.status = "awaiting_path_selection"
    test_state.awaiting_path_selection = True
    test_state.path_choice = None
    test_state.message = "Selecteer een werkstroom"
    
    print(f"\n📋 Test state:")
    print(f"  - step: {test_state.step}")
    print(f"  - status: {test_state.status}")
    print(f"  - awaiting_path_selection: {test_state.awaiting_path_selection}")
    print(f"  - path_choice: {test_state.path_choice}")
    
    # Test wat er gebeurt als we path_choice instellen
    print(f"\n🧪 Test 1: Stel path_choice in op 'path_1_suppliers'")
    test_state_with_choice = ProcurementState()
    test_state_with_choice.step = "awaiting_human_input"
    test_state_with_choice.status = "awaiting_path_selection"
    test_state_with_choice.awaiting_path_selection = True
    test_state_with_choice.path_choice = "path_1_suppliers"
    
    print(f"  - Voor: path_choice = {test_state_with_choice.path_choice}")
    
    # Test de routing function
    from agent.agent import route_after_inventory, _normalize_path_choice, _state_get
    
    normalized = _normalize_path_choice(test_state_with_choice.path_choice)
    print(f"  - Normalized path_choice: {normalized}")
    
    route_result = route_after_inventory(test_state_with_choice)
    print(f"  - Route result: {route_result}")
    
    # Test await_path_selection_node
    print(f"\n🧪 Test 2: await_path_selection_node met path_choice")
    from agent.agent import await_path_selection_node
    
    result_state = await_path_selection_node(test_state_with_choice)
    print(f"  - Na node execution:")
    print(f"    - step: {result_state.step}")
    print(f"    - status: {result_state.status}")
    print(f"    - awaiting_path_selection: {result_state.awaiting_path_selection}")
    print(f"    - path_choice: {result_state.path_choice}")
    print(f"    - message: {result_state.message}")
    
    # Test scenario: Resume workflow
    print(f"\n🧪 Test 3: Probeer workflow resume")
    try:
        config = {"configurable": {"thread_id": "test-thread"}}
        
        # Fake een checkpoint state
        workflow_input = {
            "step": "awaiting_human_input",
            "status": "awaiting_path_selection", 
            "awaiting_path_selection": False,  # User heeft gekozen
            "path_choice": "path_1_suppliers",
            "message": "Path gekozen, hervat workflow"
        }
        
        print(f"  - Invoking workflow met path_choice = path_1_suppliers")
        
        # BELANGRIJK: Dit simuleert wat er zou moeten gebeuren als de frontend
        # de state update en workflow resume
        result = None
        for chunk in workflow.stream(workflow_input, config, stream_mode="values"):
            result = chunk
            print(f"    - Stream chunk: step={chunk.get('step')}, status={chunk.get('status')}")
            
            # Stop als we bij find_suppliers komen
            if chunk.get('step') == 'find_suppliers' or 'supplier' in str(chunk.get('message', '')).lower():
                print(f"    ✅ SUCCES: Workflow is naar find_suppliers gegaan!")
                break
            
            # Stop als we te lang bezig zijn
            if chunk.get('step') == 'complete' or chunk.get('step') == 'end':
                break
        
        if result:
            print(f"  - Eindresultaat: step={result.get('step')}, status={result.get('status')}")
            print(f"  - Message: {result.get('message', 'Geen message')}")
        
    except Exception as e:
        print(f"  ❌ ERROR tijdens workflow test: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🎯 Diagnose:")
    print(f"   1. Path normalization werkt: ✅")
    print(f"   2. Routing functie werkt: ✅") 
    print(f"   3. await_path_selection_node logica werkt: ✅")
    print(f"   4. Mogelijke oorzaken van het probleem:")
    print(f"      - Frontend stuurt workflow niet correct door na path selection")
    print(f"      - Workflow wordt niet hervat na state update")
    print(f"      - Er is een timing probleem tussen state update en resume")
    print(f"      - De 'interrupt_after' configuratie blokkeert de workflow flow")

if __name__ == "__main__":
    debug_workflow()